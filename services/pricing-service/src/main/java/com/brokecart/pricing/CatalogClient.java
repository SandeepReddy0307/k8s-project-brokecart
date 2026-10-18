package com.brokecart.pricing;
import java.net.URI;
import java.net.http.HttpClient;
import java.time.Duration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.server.ResponseStatusException;
@Component
public class CatalogClient {
    public record Product(String id, String name, long priceCents, String currency, long version) {}
    private final RestClient client;
    public CatalogClient(RestClient.Builder builder,@Value("${catalog.base-url}") String baseUrl) {
        var uri = URI.create(baseUrl);
        if (!java.util.Set.of("http", "https").contains(uri.getScheme()) || uri.getHost() == null || uri.getUserInfo() != null)
            throw new IllegalArgumentException("CATALOG_BASE_URL must be an HTTP(S) server URL without credentials");
        var factory = new JdkClientHttpRequestFactory(HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build());
        factory.setReadTimeout(Duration.ofSeconds(3));
        client = builder.clone().baseUrl(baseUrl).requestFactory(factory).build();
    }
    public Product product(String id) {
        try {
            Product product = client.get().uri("/api/catalog/products/{id}", id).retrieve().body(Product.class);
            if (product == null || product.priceCents() <= 0 || !"USD".equals(product.currency()))
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Invalid catalog response");
            return product;
        } catch (HttpClientErrorException.NotFound error) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY, "Cart contains an unknown product");
        } catch (RestClientException error) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Catalog is unavailable; try again shortly");
        }
    }
}
