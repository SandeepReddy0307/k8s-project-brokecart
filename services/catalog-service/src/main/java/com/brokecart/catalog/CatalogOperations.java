package com.brokecart.catalog;
import com.brokecart.common.*;
import java.util.*;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import static com.brokecart.common.Data.*;
@RestController
public class CatalogOperations {
    private final Store store;private final Events events;private final ProductRepository repository;
    public CatalogOperations(Store store,Events events,ProductRepository repository){this.store=store;this.events=events;this.repository=repository;}
    @EventListener(ApplicationReadyEvent.class) @Transactional public void publishSeed(){store.jdbc().queryForObject("SELECT id FROM outbox_mutex WHERE id=1 FOR UPDATE",Integer.class);if(store.find("bootstrap:catalog")==null){for(var product:repository.findAll())events.emit("catalog.events","catalog.product_changed",product.getId(),store.convert(product));store.save("bootstrap:catalog",map("complete",true));}}
    @PostMapping("/api/catalog/products/{id}/price") @PreAuthorize("hasRole('OPERATOR')") @Transactional public Object price(@PathVariable String id,@RequestBody Map<String,Object> body){long price=number(body,"priceCents");require(price>0&&price<=10000000,400,"Price must be 1–10000000 cents");int changed=store.jdbc().update("UPDATE products SET price_cents=?,version=version+1 WHERE id=?",price,id);require(changed==1,404,"Product not found");var product=repository.findById(id).orElseThrow();events.emit("catalog.events","catalog.product_changed",id,store.convert(product));return product;}
}
