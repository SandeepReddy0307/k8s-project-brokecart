package com.brokecart.paymentprovider;
import com.brokecart.common.*;
import java.time.Instant;
import java.util.*;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import static com.brokecart.common.Data.*;
/** Local payment provider simulator. No card information or real financial operations. */
@RestController
public class ProviderController {
    private final Store store;
    ProviderController(Store store){this.store=store;}
    @PostMapping("/internal/provider/operations") @Transactional
    public ResponseEntity<?> operate(@RequestBody Map<String,Object> body){
        String operation=id(body,"operationId"),order=id(body,"orderId"),action=text(body,"action");require(Set.of("authorize","capture","void","refund").contains(action),400,"Invalid payment action");long amount=number(body,"amountCents");require(amount>0,400,"Invalid amount");
        String key="operation:"+operation;var prior=store.lock(key);if(prior!=null){require(text(prior,"request").equals(store.encode(body)),409,"Idempotency key reused for a different operation");return ResponseEntity.ok(resolve(prior));}
        var payment=store.lock("payment:"+order);if(payment==null)payment=map("orderId",order,"authorized",false,"captured",false,"refundedCents",0);
        String desired;
        if(action.equals("authorize")){desired=text(body,"paymentToken").equals("tok_declined")?"DECLINED":"AUTHORIZED";if(desired.equals("AUTHORIZED")){payment.put("authorized",true);payment.put("amountCents",amount);}}
        else if(action.equals("capture")){require(Boolean.TRUE.equals(payment.get("authorized"))&&!Boolean.TRUE.equals(payment.get("voided")),409,"No active authorization");require(number(payment,"amountCents")==amount,409,"Amount differs from authorization");payment.put("captured",true);desired="CAPTURED";}
        else if(action.equals("void")){require(!Boolean.TRUE.equals(payment.get("captured")),409,"Captured payments must be refunded");payment.put("voided",true);desired="VOIDED";}
        else {require(Boolean.TRUE.equals(payment.get("captured")),409,"No captured payment");require(number(payment,"refundedCents")+amount<=number(payment,"amountCents"),409,"Refund exceeds captured amount");payment.put("refundedCents",number(payment,"refundedCents")+amount);desired="REFUNDED";}
        store.save("payment:"+order,payment);boolean uncertain=action.equals("authorize")&&Set.of("tok_timeout","tok_delayed").contains(text(body,"paymentToken"));
        var result=map("operationId",operation,"orderId",order,"status",uncertain?"PENDING":desired,"desiredStatus",desired,"resolveAfter",Instant.now().plusSeconds(3).toString(),"request",store.encode(body),"providerReference",UUID.randomUUID().toString());store.save(key,result);
        // A timeout response does not roll back provider state. The caller must reconcile.
        return ResponseEntity.status(text(body,"paymentToken").equals("tok_timeout")&&action.equals("authorize")?504:uncertain?202:200).body(safe(result));
    }
    private Map<String,Object> safe(Map<String,Object> value){return map("operationId",value.get("operationId"),"orderId",value.get("orderId"),"status",value.get("status"),"providerReference",value.get("providerReference"));}
    private Map<String,Object> resolve(Map<String,Object> result){if(text(result,"status").equals("PENDING")&&Instant.parse(text(result,"resolveAfter")).isBefore(Instant.now())){result.put("status",result.get("desiredStatus"));store.save("operation:"+text(result,"operationId"),result);}return safe(result);}
    @GetMapping("/internal/provider/operations/{id}") @Transactional public Object get(@PathVariable String id){return resolve(store.get("operation:"+id));}
}
