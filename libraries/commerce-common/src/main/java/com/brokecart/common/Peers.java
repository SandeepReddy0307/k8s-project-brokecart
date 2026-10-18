package com.brokecart.common;
import java.net.URI;
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpMethod;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;
@Component
public class Peers {
    private final RestClient.Builder builder;private final String token;
    public Peers(RestClient.Builder builder,@Value("${app.internal-token}") String token){this.builder=builder;this.token=token;}
    @SuppressWarnings("unchecked") public Map<String,Object> call(String base,String method,String path,Object body){
        var uri=URI.create(base);if(!java.util.Set.of("http","https").contains(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null)throw new IllegalArgumentException("Invalid peer URL");
        var factory=new JdkClientHttpRequestFactory(HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build());factory.setReadTimeout(Duration.ofSeconds(4));
        try{var request=builder.clone().requestFactory(factory).baseUrl(base).build().method(HttpMethod.valueOf(method)).uri(path).header("X-Internal-Token",token);
            if(body!=null)request.contentType(org.springframework.http.MediaType.APPLICATION_JSON).body(body);
            var result=request.retrieve().body(Map.class);return result==null?Map.of():result;
        }catch(RestClientException error){throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"A dependency is unavailable; retry with the same idempotency key");}
    }
}
