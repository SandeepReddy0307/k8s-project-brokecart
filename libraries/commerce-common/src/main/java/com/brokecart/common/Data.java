package com.brokecart.common;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
/** JSON boundary helpers. Domain controllers validate before persisting or publishing. */
public final class Data {
    private Data() {}
    public static Map<String,Object> map(Object... pairs) {
        Map<String,Object> result = new LinkedHashMap<>();
        for(int i=0;i<pairs.length;i+=2) result.put((String)pairs[i],pairs[i+1]);
        return result;
    }
    public static String text(Map<String,Object> value, String key) { return Objects.toString(value.get(key), ""); }
    public static long number(Map<String,Object> value,String key) { Object n=value.get(key); if(!(n instanceof Number) || ((Number)n).doubleValue()!=((Number)n).longValue()) fail(400,"Invalid integer: "+key); return ((Number)n).longValue(); }
    @SuppressWarnings("unchecked") public static Map<String,Object> object(Map<String,Object> value,String key) {
        if(!(value.get(key) instanceof Map)) fail(400,"Missing object: "+key); return (Map<String,Object>)value.get(key);
    }
    @SuppressWarnings("unchecked") public static List<Map<String,Object>> lines(Map<String,Object> value,String key) {
        if(!(value.get(key) instanceof List<?> list) || list.stream().anyMatch(x->!(x instanceof Map))) fail(400,"Invalid list: "+key);
        return (List<Map<String,Object>>)value.get(key);
    }
    public static void require(boolean condition,int status,String message) { if(!condition) fail(status,message); }
    public static void fail(int status,String message) { throw new ResponseStatusException(HttpStatus.valueOf(status),message); }
    public static String id(Map<String,Object> body,String key) { String value=text(body,key);require(value.matches("[a-zA-Z0-9_-]{1,100}"),400,"Invalid "+key);return value; }
    public static void owner(Map<String,Object> value,String customer) {require(customer.equals(text(value,"customerId")),403,"This resource belongs to another customer");}
}
