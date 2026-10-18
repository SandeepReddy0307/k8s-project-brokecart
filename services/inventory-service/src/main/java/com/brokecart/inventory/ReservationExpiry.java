package com.brokecart.inventory;
import com.brokecart.common.*;
import java.time.Instant;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.*;
import static com.brokecart.common.Data.*;
@RestController
public class ReservationExpiry {
    private final Store store;private final Events events;private final Peers peers;private final TransactionTemplate tx;private final String orders;
    public ReservationExpiry(Store store,Events events,Peers peers,TransactionTemplate tx,@Value("${peers.orders}") String orders){this.store=store;this.events=events;this.peers=peers;this.tx=tx;this.orders=orders;}
    @PostMapping("/internal/inventory/expire") public Object expire(){int count=0;for(var candidate:store.all("reservation:"))if(text(candidate,"status").equals("ACTIVE")&&Instant.parse(text(candidate,"expiresAt")).isBefore(Instant.now())){
        var order=peers.call(orders,"GET","/internal/orders/"+text(candidate,"orderId"),null);if(!Set.of("RESERVING","AUTHORIZING").contains(text(order,"status")))continue;
        tx.executeWithoutResult(s->{var current=store.lock("reservation:"+text(candidate,"orderId"));if(!text(current,"status").equals("ACTIVE")||Boolean.TRUE.equals(current.get("expiryRequested")))return;current.put("expiryRequested",true);store.save("reservation:"+text(candidate,"orderId"),current);events.emit("inventory.events","inventory.expiry_requested",text(candidate,"orderId"),order);});count++;
    }return map("expired",count);}
}
