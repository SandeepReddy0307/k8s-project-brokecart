package com.brokecart.inventory;
import com.brokecart.common.*;
import java.time.Instant;
import java.util.*;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import static com.brokecart.common.Data.*;
@RestController
public class InventoryController implements EventHandler {
    private final Store store;private final Events events;
    public InventoryController(Store store,Events events){this.store=store;this.events=events;}
    @EventListener(ApplicationReadyEvent.class) @Transactional public void seed(){store.jdbc().queryForObject("SELECT id FROM outbox_mutex WHERE id=1 FOR UPDATE",Integer.class);for(int i=1;i<=8;i++){String id="bc-%03d".formatted(i);if(store.find("stock:"+id)==null)store.save("stock:"+id,map("productId",id,"available",25));}}
    @GetMapping("/api/operations/inventory") @PreAuthorize("hasRole('OPERATOR')") public Object all(){return map("items",store.all("stock:"));}
    @PostMapping("/api/operations/inventory/{product}/restock") @PreAuthorize("hasRole('OPERATOR')") @Transactional
    public Object restock(@PathVariable String product,@RequestBody Map<String,Object> body){long quantity=number(body,"quantity");require(quantity>0&&quantity<=10000,400,"Restock quantity must be 1–10000");var stock=store.lock("stock:"+product);require(stock!=null,404,"Product not found");stock.put("available",number(stock,"available")+quantity);store.save("stock:"+product,stock);return stock;}
    private void respond(String type,Event event,Map<String,Object> payload){events.emit("inventory.events",type,event.aggregateId(),payload,event.eventId());}
    @Override public void handle(Event event){
        String key="reservation:"+event.aggregateId();var reservation=store.lock(key);
        if(event.eventType().equals("inventory.reserve")){
            if(reservation!=null){respond(text(reservation,"status").equals("REJECTED")?"inventory.rejected":"inventory.reserved",event,event.payload());return;}
            var items=new ArrayList<>(lines(event.payload(),"lines"));items.sort(Comparator.comparing(x->text(x,"productId")));var stocks=new LinkedHashMap<String,Map<String,Object>>();
            for(var line:items){String id=id(line,"productId");long quantity=number(line,"quantity");require(quantity>0&&quantity<=10,400,"Invalid reservation quantity");var stock=store.lock("stock:"+id);if(stock==null||number(stock,"available")<quantity){store.save(key,map("orderId",event.aggregateId(),"status","REJECTED"));respond("inventory.rejected",event,event.payload());return;}require(!stocks.containsKey(id),400,"Duplicate reservation product");stocks.put(id,stock);}
            for(var line:items){var stock=stocks.get(text(line,"productId"));stock.put("available",number(stock,"available")-number(line,"quantity"));store.save("stock:"+text(line,"productId"),stock);}
            store.save(key,map("orderId",event.aggregateId(),"status","ACTIVE","lines",items,"expiresAt",Instant.now().plusSeconds(900).toString(),"customerId",event.payload().get("customerId")));respond("inventory.reserved",event,event.payload());
        }else if(event.eventType().equals("order.confirmed")){
            if(reservation!=null&&text(reservation,"status").equals("ACTIVE")){reservation.put("status","COMMITTED");store.save(key,reservation);}
        }else if(event.eventType().equals("inventory.release")||event.eventType().equals("inventory.restock_return")){
            if(reservation!=null&&Set.of("ACTIVE","COMMITTED").contains(text(reservation,"status"))){
                for(var line:lines(reservation,"lines")){var stock=store.lock("stock:"+text(line,"productId"));stock.put("available",number(stock,"available")+number(line,"quantity"));store.save("stock:"+text(line,"productId"),stock);}
                reservation.put("status",event.eventType().equals("inventory.restock_return")?"RETURNED":"RELEASED");store.save(key,reservation);
            }
            respond("inventory.released",event,event.payload());
        }
    }
}
