"""Read-only/application quote smoke check against running catalog/pricing processes."""
import json
import os
import urllib.request
import urllib.error

catalog = os.environ.get("CATALOG_URL", "http://127.0.0.1:8081")
pricing = os.environ.get("PRICING_URL", "http://127.0.0.1:8082")

def call(url, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)

assert call(catalog + "/actuator/health/readiness")["status"] == "UP"
assert call(pricing + "/actuator/health/readiness")["status"] == "UP"
products = call(catalog + "/api/catalog/products?size=100")
assert len(products["items"]) == 8
quote = call(pricing + "/api/pricing/quotes", {
    "items": [{"productId": "bc-001", "quantity": 1, "priceCents": 1}],
    "promoCode": "BROKE10",
})
assert quote["subtotalCents"] == 8990, "Client price must not affect server pricing"
assert quote["discountCents"] == 899
assert quote["shippingCents"] == 499
assert quote["totalCents"] == 8590
try:
    call(pricing + "/api/pricing/quotes", {"items": [{"productId": "bc-999", "quantity": 1}]})
except urllib.error.HTTPError as error:
    assert error.code == 422
else:
    raise AssertionError("Unknown products must be rejected")
print("PASS: live database/catalog HTTP, authoritative pricing, promotion, shipping, unknown-product rejection")
