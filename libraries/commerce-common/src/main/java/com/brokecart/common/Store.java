package com.brokecart.common;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;
import static com.brokecart.common.Data.*;
/** Each process uses its own database. JSON aggregates have transactional SQL row locks. */
@Component
public class Store {
    private final JdbcTemplate jdbc;
    private final ObjectMapper json;
    public Store(JdbcTemplate jdbc,ObjectMapper json){this.jdbc=jdbc;this.json=json;}
    public JdbcTemplate jdbc(){return jdbc;}
    public String encode(Object value){try{return json.writeValueAsString(value);}catch(Exception e){throw new IllegalArgumentException("Invalid document",e);}}
    public Map<String,Object> decode(String value){try{return json.readValue(value,new TypeReference<>(){});}catch(Exception e){throw new IllegalArgumentException("Invalid persisted document",e);}}
    public Map<String,Object> convert(Object value){return decode(encode(value));}
    public Map<String,Object> find(String id){var rows=jdbc.query("SELECT payload FROM documents WHERE id=?",(r,n)->decode(r.getString(1)),id);return rows.isEmpty()?null:rows.get(0);}
    public Map<String,Object> get(String id){var result=find(id);require(result!=null,404,"Resource not found");return result;}
    public Map<String,Object> lock(String id){var rows=jdbc.query("SELECT payload FROM documents WHERE id=? FOR UPDATE",(r,n)->decode(r.getString(1)),id);return rows.isEmpty()?null:rows.get(0);}
    @Transactional public void save(String id,Map<String,Object> document){if(jdbc.update("UPDATE documents SET payload=?,version=version+1 WHERE id=?",encode(document),id)==0)jdbc.update("INSERT INTO documents(id,payload) VALUES (?,?)",id,encode(document));}
    public List<Map<String,Object>> all(String prefix){return jdbc.query("SELECT payload FROM documents WHERE id LIKE ? ORDER BY id LIMIT 1000",(r,n)->decode(r.getString(1)),prefix+"%");}
    public void delete(String id){jdbc.update("DELETE FROM documents WHERE id=?",id);}
}
