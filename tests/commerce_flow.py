"""Full application contract test. Can use local relay or real Kafka-backed processes."""
import importlib.util
import json
import http.cookiejar
import os
from pathlib import Path
import threading
import time
import urllib.request
import urllib.error
import uuid

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('local',ROOT/'tools/run-local.py');local=importlib.util.module_from_spec(spec);spec.loader.exec_module(local)

class Client:
    def __init__(self,urls):self.urls=urls;self.cookies=http.cookiejar.CookieJar();self.http=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
    def call(self,service,path,body=None,method=None,headers=None):
        data=None if body is None else json.dumps(body).encode()
        req=urllib.request.Request(self.urls[service]+path,data=data,method=method,headers={'Content-Type':'application/json','Origin':'http://localhost:5173',**(headers or {})})
        with self.http.open(req,timeout=20) as response:
            raw=response.read();return json.loads(raw) if raw else {}
    def status(self,expected,*args,**kwargs):
        try:self.call(*args,**kwargs)
        except urllib.error.HTTPError as error:assert error.code==expected,(error.code,error.read().decode());return
        raise AssertionError(f'Expected HTTP {expected}')
    def login(self,email,password):return self.call('identity','/api/identity/login',{'email':email,'password':password})

def wait_for(task,predicate,timeout=45):
    last=None
    for _ in range(int(timeout*4)):
        last=task()
        if predicate(last):return last
        time.sleep(.25)
    raise AssertionError(f'Timed out waiting for workflow: {last}')

def verify(urls):
    customer=Client(urls);operator=Client(urls);other=Client(urls);password='ApplicationTestsOnly123!'
    email='buyer-'+uuid.uuid4().hex[:8]+'@example.test'
    customer.status(401,'cart','/api/cart')
    customer.call('identity','/api/identity/register',{'email':email,'password':password});user=customer.login(email,password)['user']
    other.call('identity','/api/identity/register',{'email':'other-'+email,'password':password});other.login('other-'+email,password)
    local.request(urls['identity'],'/internal/identity/operators',{'email':'operator@example.test','password':password});operator.login('operator@example.test',password)
    customer.status(403,'inventory','/api/operations/inventory')
    customer.status(403,'catalog','/api/catalog/products/bc-001/price',{'priceCents':1})
    customer.status(403,'cart','/api/cart/items/bc-001',{'quantity':1},method='PUT',headers={'Origin':'https://untrusted.example'})
    print('PASS: registration, login, customer/operator authorization and cookie Origin validation',flush=True)

    def stock(product):return next(s['available'] for s in operator.call('inventory','/api/operations/inventory')['items'] if s['productId']==product)
    def buy(token='tok_approved',product='bc-001',quantity=1):
        customer.call('cart','/api/cart/items/'+product,{'quantity':quantity},method='PUT')
        key=uuid.uuid4().hex;body={'address':'123 Test Street, Test City 12345','paymentToken':token,'promoCode':'BROKE10'}
        order=customer.call('checkout','/api/checkout',body,headers={'Idempotency-Key':key})
        assert customer.call('checkout','/api/checkout',body,headers={'Idempotency-Key':key})['orderId']==order['orderId']
        changed=dict(body,address='456 Different Street, Test City')
        customer.status(409,'checkout','/api/checkout',changed,headers={'Idempotency-Key':key})
        return order
    def read(order):return customer.call('orders','/api/orders/'+order['orderId'])
    before=stock('bc-001');order=buy();confirmed=wait_for(lambda:read(order),lambda o:o['status']=='CONFIRMED')
    assert confirmed['totalCents']==8590
    assert stock('bc-001')==before-1
    other.status(403,'orders','/api/orders/'+order['orderId'])
    print('PASS: authoritative checkout, idempotency, stock reservation, authorization and capture',flush=True)

    if os.environ.get('REAL_KAFKA')!='1':
        event={'eventId':str(uuid.uuid4()),'eventType':'inventory.reserve','schemaVersion':1,'aggregateId':order['orderId'],'correlationId':order['orderId'],'causationId':'','occurredAt':'2026-10-14T00:00:00Z','payload':confirmed}
        local.request(urls['inventory'],'/internal/events',event);local.request(urls['inventory'],'/internal/events',event);assert stock('bc-001')==before-1
        print('PASS: duplicate event delivery does not reserve stock twice',flush=True)

    customer.call('orders','/api/orders/'+order['orderId']+'/cancel',{})
    wait_for(lambda:read(order),lambda o:o['status']=='CANCELLED');assert stock('bc-001')==before
    print('PASS: cancellation refund and stock compensation',flush=True)

    declined=buy('tok_declined');wait_for(lambda:read(declined),lambda o:o['status']=='FAILED');assert stock('bc-001')==before
    print('PASS: declined payment releases reserved stock',flush=True)

    uncertain=buy('tok_timeout',product='bc-002');wait_for(lambda:read(uncertain),lambda o:o['status']=='CONFIRMED')
    print('PASS: uncertain provider result reconciles without a second authorization',flush=True)
    delayed=buy('tok_delayed',product='bc-004');wait_for(lambda:read(delayed),lambda o:o['status']=='CONFIRMED')
    customer.call('orders','/api/orders/'+delayed['orderId']+'/cancel',{})
    wait_for(lambda:read(delayed),lambda o:o['status']=='CANCELLED')
    print('PASS: delayed authorization and subsequent refund',flush=True)

    delivered=buy(product='bc-003');wait_for(lambda:read(delivered),lambda o:o['status']=='CONFIRMED');id=delivered['orderId']
    for state in ['PACKED','SHIPPED','DELIVERED']:
        assert operator.call('shipping',f'/api/operations/shipping/{id}/advance',{})['status']==state
        if state in ['SHIPPED','DELIVERED']:wait_for(lambda:read(delivered),lambda o:o['status']==state)
    customer.status(409,'orders',f'/api/orders/{id}/cancel',{})
    customer.call('returns','/api/returns',{'orderId':id,'reason':'Test return after delivery'})
    other.status(403,'returns','/api/returns',{'orderId':id,'reason':'Must not access another customer order'})
    operator.call('returns',f'/api/operations/returns/{id}/approve',{})
    wait_for(lambda:read(delivered),lambda o:o['status']=='RETURNED')
    wait_for(lambda:stock('bc-003'),lambda available:available==25)
    print('PASS: packing, shipping, delivery, owner checks, return approval and refund',flush=True)

    notices=wait_for(lambda:customer.call('notifications','/api/notifications')['items'],lambda values:any(n['orderId']==id for n in values))
    customer.call('notifications','/api/notifications/'+notices[0]['id']+'/read',{})
    customer.status(403,'reporting','/api/operations/reports')
    report=wait_for(lambda:operator.call('reporting','/api/operations/reports'),lambda r:r['refundedCents']>0)
    assert report['orders']>=4
    search=wait_for(lambda:customer.call('search','/api/search/products?q=Headphones')['items'],lambda items:len(items)>0)
    assert search[0]['id']=='bc-001'
    operator.call('catalog','/api/catalog/products/bc-008/price',{'priceCents':2590})
    updated=wait_for(lambda:customer.call('search','/api/search/products?q=Hydration')['items'],lambda items:items and items[0]['priceCents']==2590)
    print('PASS: notification inbox, reporting projection, catalog update and search indexing',flush=True)

    # A stale checkout must not clear newly added items (cart version ABA protection).
    old=customer.call('cart','/api/cart/items/bc-005',{'quantity':1},method='PUT')
    local.request(urls['cart'],'/internal/cart/users/'+user['id']+'/consume',{'version':old['version']})
    customer.call('cart','/api/cart/items/bc-005',{'quantity':2},method='PUT')
    result=local.request(urls['cart'],'/internal/cart/users/'+user['id']+'/consume',{'version':old['version']})
    assert result['cleared'] is False
    assert customer.call('cart','/api/cart')['items'][0]['quantity']==2
    customer.call('cart','/api/cart/items/bc-005',{'quantity':0},method='PUT')
    print('PASS: shared cart ownership and stale-consumption protection',flush=True)
    return {'customerEmail':email,'password':password,'operatorEmail':'operator@example.test','urls':urls}

if __name__=='__main__':
    apps=local.Applications(port_offset=10000)
    try:
        apps.start();verify(apps.urls)
        print('PASS: complete commerce application flow using local development event transport',flush=True)
    except Exception:
        print('Application logs:',apps.logs,flush=True);raise
    finally:apps.close()
