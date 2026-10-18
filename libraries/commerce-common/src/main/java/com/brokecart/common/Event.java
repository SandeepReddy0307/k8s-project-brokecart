package com.brokecart.common;
import java.time.Instant;
import java.util.Map;
public record Event(String eventId,String eventType,int schemaVersion,String aggregateId,String correlationId,String causationId,Instant occurredAt,Map<String,Object> payload) {}
