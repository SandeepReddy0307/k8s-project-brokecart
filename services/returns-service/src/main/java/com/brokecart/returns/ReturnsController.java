package com.brokecart.returns;
import com.brokecart.common.*;
import java.time.Instant;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import static com.brokecart.common.Data.*;
@RestController
public class ReturnsController implements EventHandler {
    private final Store store;private final Events events;private final Peers peers;private final String orders;
    public ReturnsController(Store store,Events events,Peers peers,@Value("${peers.orders}") String orders){this.store=store;this.events=events;this.peers=peers;this.orders=orders;}
    @PostMapping("/api/returns") @Transactional public Object create(@AuthenticationPrincipal Jwt jwt,@RequestBody Map<String,Object> body){String id=id(body,"orderId");String reason=text(body,"reason").strip();require(reason.length()>=5&&reason.length()<=500,400,"Return reason must be 5–500 characters");var order=peers.call(orders,"GET","/internal/orders/"+id,null);owner(order,jwt.getSubject());require(text(order,"status").equals("DELIVERED"),409,"Returns require a delivered order");var previous=store.lock("return:"+id);if(previous!=null)return previous;
        var result=map("returnId",UUID.randomUUID().toString(),"orderId",id,"customerId",jwt.getSubject(),"status","REQUESTED","reason",reason,"createdAt",Instant.now().toString(),"order",order);store.save("return:"+id,result);events.emit("returns.events","return.requested",id,map("orderId",id,"customerId",jwt.getSubject(),"returnId",result.get("returnId")));return result;}
    @GetMapping("/api/returns") public Object mine(@AuthenticationPrincipal Jwt jwt){return map("items",store.all("return:").stream().filter(r->jwt.getSubject().equals(text(r,"customerId"))).toList());}
    @GetMapping("/api/operations/returns") @PreAuthorize("hasRole('OPERATOR')") public Object all(){return map("items",store.all("return:"));}
    @PostMapping("/api/operations/returns/{order}/approve") @PreAuthorize("hasRole('OPERATOR')") @Transactional public Object approve(@PathVariable String order){var result=store.lock("return:"+order);require(result!=null,404,"Return not found");require(text(result,"status").equals("REQUESTED"),409,"Return has already been reviewed");result.put("status","REFUND_PENDING");store.save("return:"+order,result);var payload=new LinkedHashMap<>(object(result,"order"));payload.put("refundId",result.get("returnId"));events.emit("payments.commands","payment.refund",order,payload);return result;}
    @PostMapping("/api/operations/returns/{order}/reject") @PreAuthorize("hasRole('OPERATOR')") @Transactional public Object reject(@PathVariable String order){var result=store.lock("return:"+order);require(result!=null,404,"Return not found");require(text(result,"status").equals("REQUESTED"),409,"Return has already been reviewed");result.put("status","REJECTED");store.save("return:"+order,result);events.emit("returns.events","return.rejected",order,map("customerId",result.get("customerId"),"orderId",order));return result;}
    @Override public void handle(Event event){if(!event.eventType().equals("payment.refunded")||text(event.payload(),"refundId").equals("cancel"))return;var result=store.lock("return:"+event.aggregateId());if(result==null||!text(result,"status").equals("REFUND_PENDING"))return;result.put("status","REFUNDED");store.save("return:"+event.aggregateId(),result);events.emit("returns.events","return.refunded",event.aggregateId(),event.payload());events.emit("inventory.commands","inventory.restock_return",event.aggregateId(),event.payload());}
}
