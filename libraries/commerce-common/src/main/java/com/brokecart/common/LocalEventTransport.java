package com.brokecart.common;
import java.util.*;
import org.springframework.context.annotation.Profile;
import org.springframework.web.bind.annotation.*;
/** Internal, local-profile-only transport for application tests without Kafka. */
@RestController @Profile("local")
public class LocalEventTransport {
    private final Events events;private final List<EventHandler> handlers;
    LocalEventTransport(Events events,List<EventHandler> handlers){this.events=events;this.handlers=handlers;}
    @GetMapping("/internal/outbox") public Object outbox(){return events.pending();}
    @PostMapping("/internal/outbox/{id}/ack") public void ack(@PathVariable String id){events.ack(id);}
    @PostMapping("/internal/events") public void receive(@RequestBody Event event){if(handlers.size()!=1)throw new IllegalStateException("Service has no event handler");events.consume(event,handlers.get(0));}
}
