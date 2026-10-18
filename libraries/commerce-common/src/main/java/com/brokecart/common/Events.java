package com.brokecart.common;
import java.time.Instant;
import java.util.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;
import static com.brokecart.common.Data.*;
@Component
public class Events {
    private final Store store;
    private final ObjectMapper json;
    public Events(Store store,ObjectMapper json){this.store=store;this.json=json;}
    @Transactional public void emit(String topic,String type,String aggregate,Map<String,Object> payload){emit(topic,type,aggregate,payload,"");}
    @Transactional public void emit(String topic,String type,String aggregate,Map<String,Object> payload,String cause){
        var event=new Event(UUID.randomUUID().toString(),type,1,aggregate,aggregate,cause,Instant.now(),payload);
        store.jdbc().update("INSERT INTO event_outbox(event_id,topic,aggregate_id,payload,created_at) VALUES (?,?,?,?,?)",event.eventId(),topic,aggregate,store.encode(event),java.sql.Timestamp.from(event.occurredAt()));
    }
    @Transactional public void consume(Event event,EventHandler handler){
        require(event!=null && event.schemaVersion()==1 && event.payload()!=null && event.aggregateId()!=null && event.eventId()!=null && event.eventId().length()<=100,400,"Invalid event envelope");
        if(store.jdbc().queryForObject("SELECT count(*) FROM event_inbox WHERE event_id=?",Integer.class,event.eventId())>0)return;
        store.jdbc().update("INSERT INTO event_inbox(event_id,processed_at) VALUES (?,?)",event.eventId(),java.sql.Timestamp.from(Instant.now()));
        handler.handle(event);
    }
    public Event decode(String encoded){try{return json.readValue(encoded,Event.class);}catch(Exception e){throw new IllegalArgumentException("Invalid event JSON",e);}}
    public List<Map<String,Object>> pending(){return store.jdbc().query("SELECT event_id,topic,payload FROM event_outbox WHERE published=FALSE ORDER BY sequence_number LIMIT 100",(r,n)->map("eventId",r.getString(1),"topic",r.getString(2),"event",store.convert(decode(r.getString(3)))));}
    public void ack(String id){store.jdbc().update("UPDATE event_outbox SET published=TRUE WHERE event_id=?",id);}
}
