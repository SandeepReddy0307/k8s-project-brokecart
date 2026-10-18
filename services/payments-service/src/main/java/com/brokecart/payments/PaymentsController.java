package com.brokecart.payments;
import com.brokecart.common.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import static com.brokecart.common.Data.*;
@RestController
public class PaymentsController implements EventHandler {
    private final Store store;private final Events events;private final Peers peers;private final TransactionTemplate transaction;private final String provider;
    public PaymentsController(Store store,Events events,Peers peers,TransactionTemplate transaction,@Value("${peers.payment-provider}") String provider){this.store=store;this.events=events;this.peers=peers;this.transaction=transaction;this.provider=provider;}
    @Override public void handle(Event event){
        if(!event.eventType().startsWith("payment."))return;String action=event.eventType().substring(8);require(Set.of("authorize","capture","void","refund").contains(action),400,"Invalid payment command");
        String operation=(event.aggregateId()+"_"+action+"_"+text(event.payload(),"refundId"));var previous=store.lock("attempt:"+operation);if(previous!=null)return;
        var attempt=map("operationId",operation,"orderId",event.aggregateId(),"action",action,"status","UNKNOWN","payload",event.payload(),"request",map("operationId",operation,"orderId",event.aggregateId(),"action",action,"amountCents",number(event.payload(),"totalCents"),"paymentToken",text(event.payload(),"paymentToken")));
        store.save("attempt:"+operation,attempt);
        try{complete(attempt,peers.call(provider,"POST","/internal/provider/operations",attempt.get("request")));}
        catch(Exception error){events.emit("payments.events","payment.uncertain",event.aggregateId(),map("orderId",event.aggregateId(),"customerId",event.payload().get("customerId"),"operationId",operation));}
    }
    private void complete(Map<String,Object> attempt,Map<String,Object> outcome){
        String status=text(outcome,"status");if(status.equals("PENDING"))return;attempt.put("status",status);attempt.put("providerReference",outcome.get("providerReference"));store.save("attempt:"+text(attempt,"operationId"),attempt);
        String type=switch(status){case "AUTHORIZED"->"payment.authorized";case "CAPTURED"->"payment.captured";case "VOIDED"->"payment.voided";case "REFUNDED"->"payment.refunded";case "DECLINED"->"payment.declined";default->throw new IllegalArgumentException("Invalid provider state");};
        var payload=new LinkedHashMap<>(object(attempt,"payload"));payload.remove("paymentToken");payload.put("operationId",attempt.get("operationId"));payload.put("providerReference",outcome.get("providerReference"));events.emit("payments.events",type,text(attempt,"orderId"),payload);
    }
    @Scheduled(fixedDelay=3000,initialDelay=5000) public void reconcile(){for(var pending:store.all("attempt:"))if(text(pending,"status").equals("UNKNOWN"))transaction.executeWithoutResult(s->{var attempt=store.lock("attempt:"+text(pending,"operationId"));if(!text(attempt,"status").equals("UNKNOWN"))return;try{complete(attempt,peers.call(provider,"GET","/internal/provider/operations/"+text(attempt,"operationId"),null));}catch(Exception ignored){try{complete(attempt,peers.call(provider,"POST","/internal/provider/operations",attempt.get("request")));}catch(Exception unavailable){org.slf4j.LoggerFactory.getLogger(getClass()).warn("payment-reconciliation-pending operationId={}",attempt.get("operationId"));}}});}
    @PostMapping("/internal/payments/reconcile") public Object reconcileNow(){reconcile();return map("reconciled",true);}
    @GetMapping("/api/operations/payments") @PreAuthorize("hasRole('OPERATOR')") public Object attempts(){return map("items",store.all("attempt:").stream().map(a->map("operationId",a.get("operationId"),"orderId",a.get("orderId"),"action",a.get("action"),"status",a.get("status"))).toList());}
}
