package com.brokecart.shipping;
import com.brokecart.common.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import static com.brokecart.common.Data.*;
@RestController
public class ShippingController implements EventHandler {
    private final Store store;private final Events events;private final Peers peers;private final String orders;
    public ShippingController(Store store,Events events,Peers peers,@Value("${peers.orders}") String orders){this.store=store;this.events=events;this.peers=peers;this.orders=orders;}
    @Override public void handle(Event event){var shipment=store.lock("shipment:"+event.aggregateId());
        if(event.eventType().equals("shipping.accept")){if(shipment==null){shipment=map("orderId",event.aggregateId(),"customerId",event.payload().get("customerId"),"address",event.payload().get("address"),"status","READY","trackingNumber","BC-"+event.aggregateId().substring(0,8).toUpperCase());store.save("shipment:"+event.aggregateId(),shipment);}events.emit("shipping.events","shipping.accepted",event.aggregateId(),shipment);}
        else if(event.eventType().equals("shipping.cancel")){if(shipment!=null&&Set.of("SHIPPED","DELIVERED").contains(text(shipment,"status"))){events.emit("shipping.events","shipping.cancel_rejected",event.aggregateId(),shipment);return;}if(shipment!=null){shipment.put("status","CANCELLED");store.save("shipment:"+event.aggregateId(),shipment);}events.emit("shipping.events","shipping.cancelled",event.aggregateId(),event.payload());}
    }
    @GetMapping("/api/shipping/orders/{id}") public Object get(@AuthenticationPrincipal Jwt jwt,@PathVariable String id){var shipment=store.get("shipment:"+id);owner(shipment,jwt.getSubject());return shipment;}
    @GetMapping("/api/operations/shipping") @PreAuthorize("hasRole('OPERATOR')") public Object all(){return map("items",store.all("shipment:"));}
    @PostMapping("/api/operations/shipping/{id}/advance") @PreAuthorize("hasRole('OPERATOR')") @Transactional
    public Object advance(@PathVariable String id){var shipment=store.lock("shipment:"+id);require(shipment!=null,404,"Shipment not found");var order=peers.call(orders,"GET","/internal/orders/"+id,null);String state=text(shipment,"status");
        if(state.equals("READY")){require(text(order,"status").equals("CONFIRMED"),409,"Order payment is not confirmed");shipment.put("status","PACKED");}
        else if(state.equals("PACKED")){require(text(order,"status").equals("CONFIRMED"),409,"Order is not eligible to ship");shipment.put("status","SHIPPED");}
        else if(state.equals("SHIPPED")){shipment.put("status","DELIVERED");}
        else fail(409,"Shipment cannot advance from this state");
        store.save("shipment:"+id,shipment);String updated=text(shipment,"status");events.emit("shipping.events","shipping."+updated.toLowerCase(Locale.ROOT),id,shipment);return shipment;
    }
}
