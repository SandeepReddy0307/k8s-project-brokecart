package com.brokecart.orders;
import com.brokecart.common.*;
import java.time.Instant;
import java.util.*;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import static com.brokecart.common.Data.*;
@RestController
public class OrdersController implements EventHandler {
    private final Store store;private final Events events;
    public OrdersController(Store store,Events events){this.store=store;this.events=events;}
    private Map<String,Object> safe(Map<String,Object> order){var copy=new LinkedHashMap<>(order);copy.remove("paymentToken");return copy;}
    private void move(Map<String,Object> order,String state){order.put("status",state);var timeline=new ArrayList<>(lines(order,"timeline"));timeline.add(map("status",state,"at",Instant.now().toString()));order.put("timeline",timeline);store.save("order:"+text(order,"orderId"),order);}
    private void command(String topic,String type,Map<String,Object> order){events.emit(topic,type,text(order,"orderId"),order);}
    private void announce(String type,Map<String,Object> order){events.emit("orders.events",type,text(order,"orderId"),safe(order));}
    @PostMapping("/internal/orders") @Transactional
    public Object create(@RequestBody Map<String,Object> request){
        String customer=id(request,"customerId"),key=id(request,"idempotencyKey");String reference="idempotency:"+customer+":"+key;var previous=store.lock(reference);if(previous!=null)return safe(store.get("order:"+text(previous,"orderId")));
        var quote=object(request,"quote");require(!lines(quote,"lines").isEmpty()&&number(quote,"totalCents")>0,400,"Invalid server quote");
        String orderId=UUID.randomUUID().toString();var order=map("orderId",orderId,"customerId",customer,"email",text(request,"email"),"address",text(request,"address"),"paymentToken",text(request,"paymentToken"),"quote",quote,"lines",quote.get("lines"),"totalCents",quote.get("totalCents"),"currency","USD","timeline",new ArrayList<Map<String,Object>>(),"createdAt",Instant.now().toString());
        move(order,"RESERVING");store.save(reference,map("orderId",orderId));command("inventory.commands","inventory.reserve",order);return safe(order);
    }
    @GetMapping("/api/orders") public Object mine(@AuthenticationPrincipal Jwt jwt){return map("items",store.all("order:").stream().filter(o->jwt.getSubject().equals(text(o,"customerId"))).map(this::safe).toList());}
    @GetMapping("/api/orders/{id}") public Object get(@AuthenticationPrincipal Jwt jwt,@PathVariable String id){var order=store.get("order:"+id);owner(order,jwt.getSubject());return safe(order);}
    @GetMapping("/internal/orders/{id}") public Object internal(@PathVariable String id){return safe(store.get("order:"+id));}
    @GetMapping("/api/operations/orders") @PreAuthorize("hasRole('OPERATOR')") public Object all(){return map("items",store.all("order:").stream().map(this::safe).toList());}
    @PostMapping("/api/orders/{id}/cancel") @Transactional
    public Object cancel(@AuthenticationPrincipal Jwt jwt,@PathVariable String id){var order=store.lock("order:"+id);require(order!=null,404,"Order not found");owner(order,jwt.getSubject());require(text(order,"status").equals("CONFIRMED"),409,"Only confirmed, unshipped orders can be cancelled");move(order,"CANCELLING");command("shipping.commands","shipping.cancel",order);return safe(order);}
    private void failOrder(Map<String,Object> order,String reason,boolean voidPayment){order.put("failureReason",reason);order.put("paymentSettled",!voidPayment);order.put("inventoryReleased",false);move(order,"COMPENSATING");command("inventory.commands","inventory.release",order);if(voidPayment)command("payments.commands","payment.void",order);}
    private void finishCompensation(Map<String,Object> order){if(Boolean.TRUE.equals(order.get("paymentSettled"))&&Boolean.TRUE.equals(order.get("inventoryReleased"))){boolean cancel=Boolean.TRUE.equals(order.get("customerCancelled"));move(order,cancel?"CANCELLED":"FAILED");announce(cancel?"order.cancelled":"order.failed",order);}}
    @Override public void handle(Event event){
        var order=store.lock("order:"+event.aggregateId());if(order==null)return;String status=text(order,"status");
        switch(event.eventType()){
            case "inventory.reserved" -> {if(status.equals("RESERVING")){move(order,"AUTHORIZING");command("payments.commands","payment.authorize",order);}}
            case "inventory.expiry_requested" -> {if(Set.of("RESERVING","AUTHORIZING").contains(status))failOrder(order,"Inventory reservation expired",status.equals("AUTHORIZING"));}
            case "inventory.rejected" -> {if(status.equals("RESERVING")){order.put("failureReason","Insufficient stock");move(order,"FAILED");announce("order.failed",order);}}
            case "payment.authorized" -> {if(status.equals("AUTHORIZING")){move(order,"FULFILLING");command("shipping.commands","shipping.accept",order);}}
            case "payment.declined" -> {if(status.equals("AUTHORIZING"))failOrder(order,"Payment declined",false);}
            case "shipping.accepted" -> {if(status.equals("FULFILLING")){move(order,"CAPTURING");command("payments.commands","payment.capture",order);}}
            case "shipping.rejected" -> {if(status.equals("FULFILLING"))failOrder(order,"Fulfillment rejected",true);}
            case "payment.captured" -> {if(status.equals("CAPTURING")){move(order,"CONFIRMED");announce("order.confirmed",order);}}
            case "payment.capture_failed" -> {if(status.equals("CAPTURING")){failOrder(order,"Capture failed",true);command("shipping.commands","shipping.cancel",order);}}
            case "shipping.cancelled" -> {if(status.equals("CANCELLING")){order.put("customerCancelled",true);order.put("paymentSettled",false);order.put("inventoryReleased",false);move(order,"COMPENSATING");var payload=new LinkedHashMap<>(order);payload.put("refundId","cancel");events.emit("payments.commands","payment.refund",event.aggregateId(),payload);command("inventory.commands","inventory.release",order);}}
            case "shipping.cancel_rejected" -> {if(status.equals("CANCELLING")){move(order,"CONFIRMED");announce("order.cancellation_rejected",order);}}
            case "inventory.released" -> {if(status.equals("COMPENSATING")){order.put("inventoryReleased",true);store.save("order:"+event.aggregateId(),order);finishCompensation(order);}}
            case "payment.voided" -> {if(status.equals("COMPENSATING")){order.put("paymentSettled",true);store.save("order:"+event.aggregateId(),order);finishCompensation(order);}}
            case "payment.refunded" -> {if(status.equals("COMPENSATING")&&text(event.payload(),"refundId").equals("cancel")){order.put("paymentSettled",true);store.save("order:"+event.aggregateId(),order);finishCompensation(order);}}
            case "shipping.shipped" -> {if(status.equals("CONFIRMED")||status.equals("CANCELLING")){move(order,"SHIPPED");announce("order.shipped",order);}}
            case "shipping.delivered" -> {if(status.equals("SHIPPED")){move(order,"DELIVERED");announce("order.delivered",order);}}
            case "return.refunded" -> {if(status.equals("DELIVERED")){move(order,"RETURNED");announce("order.returned",order);}}
            default -> { /* Events irrelevant to the current lifecycle do not mutate it. */ }
        }
    }
}
