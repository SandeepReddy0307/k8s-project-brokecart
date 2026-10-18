package com.brokecart.common;
import java.time.Instant;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringBootConfiguration;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.test.context.ActiveProfiles;
import static org.junit.jupiter.api.Assertions.*;
@SpringBootTest(classes=EventsTest.App.class,properties={"spring.application.name=common-tests","spring.config.import=classpath:brokecart-common.yaml,classpath:brokecart-local.yaml"})
@ActiveProfiles("local")
class EventsTest {
    @SpringBootConfiguration @EnableAutoConfiguration @ComponentScan("com.brokecart.common") static class App {}
    @Autowired Events events;@Autowired Store store;
    Event event(){return new Event(UUID.randomUUID().toString(),"test.created",1,"test-order","test-order","",Instant.now(),Map.of());}
    @Test void duplicateDeliveryHasOnlyOneSideEffect(){var event=event();int[] calls={0};events.consume(event,e->{calls[0]++;store.save("result:duplicate",Data.map("applied",true));});events.consume(event,e->calls[0]++);assertEquals(1,calls[0]);}
    @Test void failureRollsBackInboxDomainWriteAndOutbox(){var event=event();assertThrows(IllegalStateException.class,()->events.consume(event,e->{store.save("result:rollback",Data.map("applied",true));events.emit("test.events","test.done","test-order",Map.of());throw new IllegalStateException("Injected fault");}));assertNull(store.find("result:rollback"));assertEquals(0,store.jdbc().queryForObject("SELECT count(*) FROM event_inbox WHERE event_id=?",Integer.class,event.eventId()));assertEquals(0,store.jdbc().queryForObject("SELECT count(*) FROM event_outbox WHERE topic='test.events'",Integer.class));events.consume(event,e->store.save("result:recovered",Data.map("applied",true)));assertNotNull(store.find("result:recovered"));}
}
