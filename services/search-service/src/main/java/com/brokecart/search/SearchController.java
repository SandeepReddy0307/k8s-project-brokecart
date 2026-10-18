package com.brokecart.search;
import com.brokecart.common.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.HttpClientErrorException;
import static com.brokecart.common.Data.*;
@RestController
public class SearchController implements EventHandler {
    private final Store store;private final Peers peers;private final TransactionTemplate transaction;private final String catalog,backend;private final RestClient elastic;
    public SearchController(Store store,Peers peers,TransactionTemplate transaction,RestClient.Builder builder,@Value("${peers.catalog}") String catalog,@Value("${search.backend}") String backend,@Value("${search.elasticsearch-url}") String url,@Value("${search.username}") String user,@Value("${search.password}") String password){this.store=store;this.peers=peers;this.transaction=transaction;this.catalog=catalog;this.backend=backend;var factory=new org.springframework.http.client.JdkClientHttpRequestFactory(java.net.http.HttpClient.newBuilder().connectTimeout(java.time.Duration.ofSeconds(2)).build());factory.setReadTimeout(java.time.Duration.ofSeconds(5));elastic=builder.clone().requestFactory(factory).baseUrl(url).defaultHeaders(h->{if(!password.isEmpty())h.setBasicAuth(user,password);}).build();}
    private void index(Map<String,Object> product){String id=id(product,"id");store.jdbc().queryForObject("SELECT id FROM outbox_mutex WHERE id=1 FOR UPDATE",Integer.class);var previous=store.lock("product:"+id);if(previous!=null&&number(previous,"version")>number(product,"version"))return;if(backend.equals("elasticsearch")){
        try{elastic.put().uri("/brokecart-products").contentType(org.springframework.http.MediaType.APPLICATION_JSON).body(map("mappings",map("properties",map("name",map("type","text"),"description",map("type","text"),"category",map("type","keyword"))))).retrieve().toBodilessEntity();}catch(HttpClientErrorException.BadRequest existing){/* Existing index: the idempotent document PUT below still validates access. */}
        elastic.put().uri("/brokecart-products/_doc/{id}?refresh=wait_for",id).contentType(org.springframework.http.MediaType.APPLICATION_JSON).body(product).retrieve().toBodilessEntity();
    }store.save("product:"+id,product);}
    @Override public void handle(Event event){if(event.eventType().equals("catalog.product_changed"))index(event.payload());}
    @Scheduled(fixedDelay=60000,initialDelay=5000) public void reconcile(){try{var products=peers.call(catalog,"GET","/api/catalog/products?size=100",null);for(var product:lines(products,"items"))transaction.executeWithoutResult(s->index(product));}catch(Exception unavailable){org.slf4j.LoggerFactory.getLogger(getClass()).warn("search-index-reconciliation-pending");}}
    @GetMapping("/api/search/products") @SuppressWarnings("unchecked") public Object search(@RequestParam(defaultValue="") String q){require(q.length()<=100,400,"Search query is too long");if(q.isBlank())return map("items",List.of());
        if(backend.equals("elasticsearch")){var result=elastic.post().uri("/brokecart-products/_search").contentType(org.springframework.http.MediaType.APPLICATION_JSON).body(map("size",100,"query",map("multi_match",map("query",q,"fields",List.of("name^3","description"),"fuzziness","AUTO")))).retrieve().body(Map.class);var hits=(Map<String,Object>)result.get("hits");return map("items",lines(hits,"hits").stream().map(h->h.get("_source")).toList());}
        String normalized=q.toLowerCase(Locale.ROOT);return map("items",store.all("product:").stream().filter(p->(text(p,"name")+" "+text(p,"description")).toLowerCase(Locale.ROOT).contains(normalized)).toList());
    }
}
