package com.brokecart.common;
import java.util.concurrent.TimeUnit;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.*;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.listener.*;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.backoff.FixedBackOff;
@Configuration
@ConditionalOnProperty(name="app.kafka.enabled",havingValue="true")
public class KafkaTransport {
    @Bean public ConcurrentKafkaListenerContainerFactory<String,String> kafkaListenerContainerFactory(ConsumerFactory<String,String> consumerFactory,KafkaTemplate<String,String> template){
        var factory=new ConcurrentKafkaListenerContainerFactory<String,String>();factory.setConsumerFactory(consumerFactory);
        var recoverer=new DeadLetterPublishingRecoverer(template,(record,error)->new org.apache.kafka.common.TopicPartition(record.topic()+".DLT",record.partition()));recoverer.setFailIfSendResultIsError(true);
        var errors=new DefaultErrorHandler(recoverer,new FixedBackOff(1000,3));factory.setCommonErrorHandler(errors);
        factory.getContainerProperties().setAckMode(ContainerProperties.AckMode.RECORD);factory.getContainerProperties().setObservationEnabled(true);return factory;
    }
    @Bean public OutboxPublisher outboxPublisher(Store store,KafkaTemplate<String,String> template){return new OutboxPublisher(store,template);}
    public static class OutboxPublisher {
        private final Store store;private final KafkaTemplate<String,String> template;
        OutboxPublisher(Store store,KafkaTemplate<String,String> template){this.store=store;this.template=template;this.template.setObservationEnabled(true);}
        @Scheduled(fixedDelay=1000) @Transactional public void publish(){
            // One publisher per service DB preserves aggregate ordering across replicas.
            if(store.jdbc().query("SELECT id FROM outbox_mutex WHERE id=1 FOR UPDATE SKIP LOCKED",(r,n)->r.getInt(1)).isEmpty())return;
            // Publish-then-commit can duplicate; inbox deduplicates.
            var batch=store.jdbc().query("SELECT event_id,topic,aggregate_id,payload FROM event_outbox WHERE published=FALSE ORDER BY sequence_number LIMIT 20 FOR UPDATE SKIP LOCKED",(r,n)->new String[]{r.getString(1),r.getString(2),r.getString(3),r.getString(4)});
            for(var row:batch){try{template.send(row[1],row[2],row[3]).get(10,TimeUnit.SECONDS);store.jdbc().update("UPDATE event_outbox SET published=TRUE WHERE event_id=?",row[0]);}catch(Exception e){throw new IllegalStateException("Outbox delivery will retry",e);}}
        }
    }
    @Component @org.springframework.boot.autoconfigure.condition.ConditionalOnExpression("${app.kafka.enabled:false} and ${app.kafka.consumer:false}")
    public static class Consumer {
        private final Events events;private final EventHandler handler;
        Consumer(Events events,EventHandler handler){this.events=events;this.handler=handler;}
        @KafkaListener(topics="#{'${app.kafka.topics}'.split(',')}")
        public void receive(String message){events.consume(events.decode(message),handler);}
    }
}
