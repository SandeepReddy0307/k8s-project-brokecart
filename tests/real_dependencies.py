"""Disposable application integration fixtures, not a deployment/cluster setup."""
import base64
import json
import os
import socket
import subprocess
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path
import commerce_flow as flow

def docker(*args,input=None):
    return subprocess.check_output(['docker',*args],input=input,text=True,stderr=subprocess.STDOUT).strip()

class Dependencies:
    def __init__(self):self.prefix='brokecart-test-'+uuid.uuid4().hex[:8];self.names=[];self.password=uuid.uuid4().hex;self.network=self.prefix;self.brokers=[]
    def container(self,suffix,image,port=None,env=None,memory=None):
        name=self.prefix+'-'+suffix;args=['run','-d','--name',name,'--label','brokecart.test='+self.prefix,'--network',self.network]
        if port:args+=['-p',f'127.0.0.1::{port}']
        if memory:args+=['--memory',memory]
        for key,value in (env or {}).items():args+=['-e',key+'='+str(value)]
        docker(*args,image);self.names.append(name)
        if port:return name,int(docker('port',name,str(port)).rsplit(':',1)[1])
        return name
    def start(self):
        docker('network','create',self.network)
        self.pg,self.pg_port=self.container('postgres','postgres:16-alpine',5432,{'POSTGRES_PASSWORD':self.password})
        self.redis,self.redis_port=self.container('redis','redis:7.4-alpine',6379)
        self.es,self.es_port=self.container('elastic','docker.elastic.co/elasticsearch/elasticsearch:8.17.6',9200,{'discovery.type':'single-node','xpack.security.enabled':'true','xpack.security.http.ssl.enabled':'false','ELASTIC_PASSWORD':self.password,'ES_JAVA_OPTS':'-Xms256m -Xmx256m'},'1536m')
        voters=','.join(f'{i}@{self.prefix}-kafka{i}:9093' for i in range(1,4));cluster=base64.urlsafe_b64encode(uuid.uuid4().bytes).decode().rstrip('=')
        for i in range(1,4):
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            name=self.prefix+f'-kafka{i}'
            env={'KAFKA_NODE_ID':str(i),'KAFKA_PROCESS_ROLES':'broker,controller','KAFKA_CONTROLLER_QUORUM_VOTERS':voters,'KAFKA_CONTROLLER_LISTENER_NAMES':'CONTROLLER','KAFKA_LISTENERS':'EXTERNAL://:9092,INTERNAL://:9094,CONTROLLER://:9093','KAFKA_ADVERTISED_LISTENERS':f'EXTERNAL://127.0.0.1:{port},INTERNAL://{name}:9094','KAFKA_LISTENER_SECURITY_PROTOCOL_MAP':'EXTERNAL:PLAINTEXT,INTERNAL:PLAINTEXT,CONTROLLER:PLAINTEXT','KAFKA_INTER_BROKER_LISTENER_NAME':'INTERNAL','KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR':'3','KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR':'3','KAFKA_TRANSACTION_STATE_LOG_MIN_ISR':'2','KAFKA_MIN_INSYNC_REPLICAS':'2','KAFKA_NUM_PARTITIONS':'3','KAFKA_DEFAULT_REPLICATION_FACTOR':'3','KAFKA_HEAP_OPTS':'-Xms128m -Xmx256m','CLUSTER_ID':cluster}
            args=['run','-d','--name',name,'--label','brokecart.test='+self.prefix,'--network',self.network,'--memory','768m','-p',f'127.0.0.1:{port}:9092']
            for k,v in env.items():args+=['-e',k+'='+v]
            docker(*args,'apache/kafka:3.9.1');self.names.append(name);self.brokers.append((name,port))
        for _ in range(90):
            try:docker('exec',self.pg,'pg_isready','-U','postgres');break
            except subprocess.CalledProcessError:time.sleep(1)
        else:raise RuntimeError('PostgreSQL did not start')
        sql=''
        for name in flow.local.NAMES:
            db=name.replace('-','')+'db';role=name.replace('-','')+'_app'
            sql+=f"CREATE ROLE {role} LOGIN PASSWORD '{self.password}'; CREATE DATABASE {db} OWNER {role}; REVOKE CONNECT ON DATABASE {db} FROM PUBLIC; GRANT CONNECT ON DATABASE {db} TO {role};\n"
        docker('exec','-i',self.pg,'psql','-U','postgres','-v','ON_ERROR_STOP=1',input=sql)
        for _ in range(120):
            try:docker('exec',self.brokers[0][0],'/opt/kafka/bin/kafka-topics.sh','--bootstrap-server','127.0.0.1:9094','--list');break
            except subprocess.CalledProcessError:time.sleep(1)
        else:raise RuntimeError('Kafka did not form its quorum')
        for topic in flow.local.TOPICS:
            for actual in [topic,topic+'.DLT']:
                docker('exec',self.brokers[0][0],'/opt/kafka/bin/kafka-topics.sh','--bootstrap-server','127.0.0.1:9094','--create','--topic',actual,'--partitions','3','--replication-factor','3','--config','min.insync.replicas=2')
        print('Ready: isolated PostgreSQL databases, Redis, Elasticsearch, three Kafka nodes / three partitions / RF3 / minISR2',flush=True)
        auth=base64.b64encode(('elastic:'+self.password).encode()).decode()
        for _ in range(90):
            try:urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{self.es_port}',headers={'Authorization':'Basic '+auth}),timeout=2);break
            except Exception:time.sleep(1)
        else:raise RuntimeError('Elasticsearch authentication/readiness failed')
        self.private=subprocess.check_output(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048'],stderr=subprocess.DEVNULL).decode()
        self.public=subprocess.check_output(['openssl','pkey','-pubout'],input=self.private.encode(),stderr=subprocess.DEVNULL).decode()
        return self
    def environment(self,name):
        return {'SPRING_PROFILES_ACTIVE':'','SPRING_DATASOURCE_URL':f'jdbc:postgresql://127.0.0.1:{self.pg_port}/{name.replace("-","")}db','SPRING_DATASOURCE_USERNAME':name.replace('-','')+'_app','SPRING_DATASOURCE_PASSWORD':self.password,'DB_URL':f'jdbc:postgresql://127.0.0.1:{self.pg_port}/{name.replace("-","")}db','DB_USER':name.replace('-','')+'_app','DB_PASSWORD':self.password,'JWT_PUBLIC_KEY':self.public,'JWT_PRIVATE_KEY':self.private if name=='identity' else '', 'INTERNAL_TOKEN':flow.local.TOKEN,'PUBLIC_ORIGIN':'http://localhost:5173','COOKIE_SECURE':'false','KAFKA_ENABLED':'true','KAFKA_BOOTSTRAP_SERVERS':','.join(f'127.0.0.1:{port}' for _,port in self.brokers),'REDIS_ENABLED':'true','REDIS_URL':f'redis://127.0.0.1:{self.redis_port}','SEARCH_BACKEND':'elasticsearch','ELASTICSEARCH_URL':f'http://127.0.0.1:{self.es_port}','ELASTICSEARCH_USERNAME':'elastic','ELASTICSEARCH_PASSWORD':self.password,'MANAGEMENT_TRACING_ENABLED':'false'}
    def close(self):
        for name in reversed(self.names):
            try:
                label=docker('inspect','-f','{{index .Config.Labels "brokecart.test"}}',name)
                if label==self.prefix:docker('rm','-f','-v',name)
            except subprocess.CalledProcessError:pass
        try:docker('network','rm',self.network)
        except subprocess.CalledProcessError:pass

if __name__=='__main__':
    deps=Dependencies();apps=None
    try:
        deps.start();apps=flow.local.Applications(port_offset=11000,environment=deps.environment);apps.start(relay=False)
        os.environ['REAL_KAFKA']='1';flow.verify(apps.urls)
        description=docker('exec',deps.brokers[0][0],'/opt/kafka/bin/kafka-topics.sh','--bootstrap-server','127.0.0.1:9094','--describe','--topic','orders.events')
        assert 'PartitionCount: 3' in description and 'ReplicationFactor: 3' in description
        print('PASS: actual Kafka-backed workflow and replicated topic topology',flush=True)
        docker('exec','-i',deps.brokers[0][0],'/opt/kafka/bin/kafka-console-producer.sh','--bootstrap-server','127.0.0.1:9094','--topic','inventory.commands',input='invalid-test-event\n')
        dead=docker('exec',deps.brokers[0][0],'/opt/kafka/bin/kafka-console-consumer.sh','--bootstrap-server','127.0.0.1:9094','--topic','inventory.commands.DLT','--from-beginning','--max-messages','1','--timeout-ms','20000')
        assert 'invalid-test-event' in dead
        print('PASS: poison event reaches its dead-letter topic',flush=True)
        for task in ['expire-reservations','reconcile-payments']:
            env=dict(os.environ,TASK=task,INTERNAL_TOKEN=flow.local.TOKEN,INVENTORY_URL=apps.urls['inventory'],PAYMENTS_URL=apps.urls['payments'])
            subprocess.run(['java','-jar',str(flow.ROOT/'services/maintenance-worker/target/maintenance-worker-0.1.0-SNAPSHOT.jar')],env=env,check=True)
        print('PASS: both one-shot maintenance tasks',flush=True)
        # Internal local test-transport endpoints must be absent in the normal profile.
        caller=flow.Client(apps.urls);caller.status(404,'orders','/internal/outbox',headers={'X-Internal-Token':flow.local.TOKEN})
        print('PASS: normal profile has no HTTP event relay endpoints',flush=True)
        docker('stop',deps.brokers[2][0]);print('Stopped one Kafka node; verifying a new order with remaining ISR',flush=True)
        customer=flow.Client(apps.urls);password='KafkaFailoverTests123!';email='failover@example.test'
        customer.call('identity','/api/identity/register',{'email':email,'password':password});customer.login(email,password)
        customer.call('cart','/api/cart/items/bc-006',{'quantity':1},method='PUT')
        order=customer.call('checkout','/api/checkout',{'address':'123 Failover Street, Local City','paymentToken':'tok_approved'},headers={'Idempotency-Key':uuid.uuid4().hex})
        flow.wait_for(lambda:customer.call('orders','/api/orders/'+order['orderId']),lambda o:o['status']=='CONFIRMED',timeout=90)
        print('PASS: purchase succeeds with one Kafka node stopped',flush=True)
    except Exception:
        if apps:print('Application logs:',apps.logs,flush=True)
        for name in deps.names:
            try:Path('/tmp/'+name+'.log').write_text(docker('logs','--tail','100',name))
            except subprocess.CalledProcessError:pass
        raise
    finally:
        if apps:apps.close()
        deps.close()
