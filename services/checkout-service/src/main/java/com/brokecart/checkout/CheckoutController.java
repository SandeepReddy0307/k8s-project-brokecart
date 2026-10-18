package com.brokecart.checkout;
import com.brokecart.common.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import static com.brokecart.common.Data.*;
@RestController
public class CheckoutController {
    private final Store store;private final Peers peers;private final String cart,pricing,orders;
    CheckoutController(Store store,Peers peers,@Value("${peers.cart}") String cart,@Value("${peers.pricing}") String pricing,@Value("${peers.orders}") String orders){this.store=store;this.peers=peers;this.cart=cart;this.pricing=pricing;this.orders=orders;}
    @PostMapping("/api/checkout") @Transactional
    public Object checkout(@AuthenticationPrincipal Jwt jwt,@RequestHeader("Idempotency-Key") String key,@RequestBody Map<String,Object> body){
        require(key.matches("[a-zA-Z0-9_-]{8,80}"),400,"Invalid idempotency key");String address=text(body,"address").strip();require(address.length()>=10&&address.length()<=300,400,"Provide a delivery address of 10–300 characters");String token=text(body,"paymentToken");require(Set.of("tok_approved","tok_declined","tok_timeout","tok_delayed").contains(token),400,"Use a simulator payment token; never send card data");
        String reference="checkout:"+jwt.getSubject()+":"+key;var previous=store.lock(reference);if(previous!=null){require(text(previous,"requestFingerprint").equals(store.encode(body)),409,"Idempotency key reused with different checkout details");return object(previous,"response");}
        var snapshot=peers.call(cart,"GET","/internal/cart/users/"+jwt.getSubject(),null);require(!lines(snapshot,"items").isEmpty(),422,"Your cart is empty");
        var quote=peers.call(pricing,"POST","/api/pricing/quotes",map("items",snapshot.get("items"),"promoCode",text(body,"promoCode")));
        var response=peers.call(orders,"POST","/internal/orders",map("idempotencyKey",key,"customerId",jwt.getSubject(),"email",jwt.getClaimAsString("email"),"address",address,"paymentToken",token,"quote",quote));store.save(reference,map("requestFingerprint",store.encode(body),"response",response));
        // Compare version so newly added items are never erased by an older checkout.
        try{peers.call(cart,"POST","/internal/cart/users/"+jwt.getSubject()+"/consume",map("version",snapshot.get("version")));}catch(Exception ignored){org.slf4j.LoggerFactory.getLogger(getClass()).warn("cart-consumption-deferred orderId={}",response.get("orderId"));}
        return response;
    }
}
