package com.brokecart.cart;
import com.brokecart.common.*;
import java.time.Instant;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import static com.brokecart.common.Data.*;
@RestController
public class CartController {
    private final Store store;private final Peers peers;private final StringRedisTemplate redis;private final boolean redisEnabled;private final String catalog;
    public CartController(Store store,Peers peers,StringRedisTemplate redis,@Value("${app.redis.enabled}") boolean enabled,@Value("${peers.catalog}") String catalog){this.store=store;this.peers=peers;this.redis=redis;this.redisEnabled=enabled;this.catalog=catalog;}
    private String key(String customer){return "cart:"+customer;}
    private Map<String,Object> snapshot(String customer){
        if(redisEnabled){var entries=redis.opsForHash().entries(key(customer));var items=new ArrayList<Map<String,Object>>();for(var entry:entries.entrySet())if(!entry.getKey().equals("version"))items.add(map("productId",entry.getKey(),"quantity",Integer.parseInt(entry.getValue().toString())));items.sort(Comparator.comparing(x->text(x,"productId")));return map("version",Long.parseLong(Objects.toString(entries.get("version"),"0")),"items",items);}
        var doc=store.find(key(customer));if(doc==null||number(doc,"expiresAt")<Instant.now().getEpochSecond())return map("version",0,"items",List.of());return map("version",doc.get("version"),"items",doc.get("items"));
    }
    @GetMapping("/api/cart") public Object get(@AuthenticationPrincipal Jwt jwt){return snapshot(jwt.getSubject());}
    @PutMapping("/api/cart/items/{product}") @Transactional
    public Object update(@AuthenticationPrincipal Jwt jwt,@PathVariable String product,@RequestBody Map<String,Object> body){
        require(product.matches("bc-[0-9]{3}"),400,"Invalid product");long quantity=number(body,"quantity");require(quantity>=0&&quantity<=10,400,"Quantity must be 0–10");if(quantity>0)peers.call(catalog,"GET","/api/catalog/products/"+product,null);
        if(redisEnabled){redis.execute(new DefaultRedisScript<Long>("if tonumber(ARGV[2])==0 then redis.call('HDEL',KEYS[1],ARGV[1]) else redis.call('HSET',KEYS[1],ARGV[1],ARGV[2]) end; redis.call('HINCRBY',KEYS[1],'version',1); redis.call('EXPIRE',KEYS[1],604800); return 1",Long.class),List.of(key(jwt.getSubject())),product,Long.toString(quantity));}
        else {var snapshot=snapshot(jwt.getSubject());var items=new ArrayList<>(lines(snapshot,"items"));items.removeIf(item->text(item,"productId").equals(product));if(quantity>0)items.add(map("productId",product,"quantity",quantity));store.save(key(jwt.getSubject()),map("version",number(snapshot,"version")+1,"items",items,"expiresAt",Instant.now().plusSeconds(604800).getEpochSecond()));}
        return snapshot(jwt.getSubject());
    }
    @GetMapping("/internal/cart/users/{customer}") public Object internalGet(@PathVariable String customer){return snapshot(customer);}
    @PostMapping("/internal/cart/users/{customer}/consume") @Transactional
    public Object consume(@PathVariable String customer,@RequestBody Map<String,Object> body){
        long version=number(body,"version");boolean cleared;
        if(redisEnabled){Long result=redis.execute(new DefaultRedisScript<Long>("local v=tonumber(redis.call('HGET',KEYS[1],'version') or '0'); if v~=tonumber(ARGV[1]) then return 0 end; redis.call('DEL',KEYS[1]); redis.call('HSET',KEYS[1],'version',v+1); redis.call('EXPIRE',KEYS[1],604800); return 1",Long.class),List.of(key(customer)),Long.toString(version));cleared=Long.valueOf(1).equals(result);}
        else {var snap=snapshot(customer);cleared=number(snap,"version")==version;if(cleared)store.save(key(customer),map("version",version+1,"items",List.of(),"expiresAt",Instant.now().plusSeconds(604800).getEpochSecond()));}
        return map("cleared",cleared);
    }
}
