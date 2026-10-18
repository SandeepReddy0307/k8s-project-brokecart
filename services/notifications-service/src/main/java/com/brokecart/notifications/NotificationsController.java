package com.brokecart.notifications;
import com.brokecart.common.*;
import java.time.Instant;
import java.util.*;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import static com.brokecart.common.Data.*;
@RestController
public class NotificationsController implements EventHandler {
    private final Store store;
    public NotificationsController(Store store){this.store=store;}
    @Override public void handle(Event event){String customer=text(event.payload(),"customerId");if(customer.isEmpty())return;store.save("notification:"+event.eventId(),map("id",event.eventId(),"customerId",customer,"orderId",event.aggregateId(),"type",event.eventType(),"message",event.eventType().replace('.',' ').replace('_',' '),"createdAt",Instant.now().toString(),"read",false));}
    @GetMapping("/api/notifications") public Object mine(@AuthenticationPrincipal Jwt jwt){return map("items",store.all("notification:").stream().filter(n->jwt.getSubject().equals(text(n,"customerId"))).sorted(Comparator.comparing((Map<String,Object> n)->text(n,"createdAt")).reversed()).toList());}
    @PostMapping("/api/notifications/{id}/read") @Transactional public Object read(@AuthenticationPrincipal Jwt jwt,@PathVariable String id){var notification=store.lock("notification:"+id);require(notification!=null,404,"Notification not found");owner(notification,jwt.getSubject());notification.put("read",true);store.save("notification:"+id,notification);return notification;}
}
