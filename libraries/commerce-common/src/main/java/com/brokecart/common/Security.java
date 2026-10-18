package com.brokecart.common;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.interfaces.RSAPublicKey;
import java.security.spec.X509EncodedKeySpec;
import java.util.*;
import javax.crypto.spec.SecretKeySpec;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.*;
import org.springframework.core.env.Environment;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.core.*;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.*;
import org.springframework.security.oauth2.server.resource.authentication.*;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.oauth2.server.resource.web.authentication.BearerTokenAuthenticationFilter;
import org.springframework.web.filter.OncePerRequestFilter;
@Configuration @EnableMethodSecurity
public class Security {
    public static final String LOCAL_KEY="BrokeCart-development-signing-key-not-for-deployment-2026";
    @Bean public JwtDecoder jwtDecoder(Environment environment,@Value("${app.jwt-public-key:}") String pem)throws Exception{
        NimbusJwtDecoder decoder;
        if(Arrays.asList(environment.getActiveProfiles()).contains("local"))decoder=NimbusJwtDecoder.withSecretKey(new SecretKeySpec(LOCAL_KEY.getBytes(StandardCharsets.UTF_8),"HmacSHA256")).macAlgorithm(MacAlgorithm.HS256).build();
        else {String raw=pem.replace("-----BEGIN PUBLIC KEY-----","").replace("-----END PUBLIC KEY-----","").replaceAll("\\s","");decoder=NimbusJwtDecoder.withPublicKey((RSAPublicKey)KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(Base64.getDecoder().decode(raw)))).build();}
        decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(JwtValidators.createDefaultWithIssuer("brokecart-identity"),jwt->jwt.getAudience().contains("brokecart")?OAuth2TokenValidatorResult.success():OAuth2TokenValidatorResult.failure(new OAuth2Error("invalid_token","Invalid audience",null))));return decoder;
    }
    @Bean public SecurityFilterChain chain(HttpSecurity http,JwtDecoder decoder,@Value("${app.internal-token}") String token,@Value("${app.public-origin}") String origin)throws Exception{
        if(token.length()<32)throw new IllegalArgumentException("INTERNAL_TOKEN must have at least 32 characters");
        var converter=new JwtAuthenticationConverter();var roles=new JwtGrantedAuthoritiesConverter();roles.setAuthoritiesClaimName("roles");roles.setAuthorityPrefix("ROLE_");converter.setJwtGrantedAuthoritiesConverter(roles);
        http.csrf(csrf->csrf.disable()).sessionManagement(s->s.sessionCreationPolicy(SessionCreationPolicy.STATELESS));
        http.addFilterBefore(new OncePerRequestFilter(){protected void doFilterInternal(HttpServletRequest req,HttpServletResponse res,FilterChain next)throws ServletException,IOException{
            if(req.getRequestURI().startsWith("/internal/")&&!java.security.MessageDigest.isEqual(token.getBytes(StandardCharsets.UTF_8),Objects.toString(req.getHeader("X-Internal-Token"),"").getBytes(StandardCharsets.UTF_8))){res.sendError(401);return;}
            boolean cookie=Arrays.stream(Optional.ofNullable(req.getCookies()).orElse(new Cookie[0])).anyMatch(c->c.getName().equals("bc_session"));
            if(cookie&&!Set.of("GET","HEAD","OPTIONS").contains(req.getMethod())&&!origin.equals(req.getHeader("Origin"))){res.sendError(403);return;}
            next.doFilter(req,res);
        }},BearerTokenAuthenticationFilter.class);
        http.authorizeHttpRequests(a->a.requestMatchers("/internal/**","/actuator/health/**","/actuator/prometheus","/api/identity/register","/api/identity/login","/api/identity/logout","/api/catalog/**","/api/pricing/**","/api/search/**","/error").permitAll().anyRequest().authenticated());
        http.oauth2ResourceServer(o->o.jwt(j->j.decoder(decoder).jwtAuthenticationConverter(converter)).bearerTokenResolver(req->{String authorization=req.getHeader("Authorization");if(authorization!=null&&authorization.startsWith("Bearer "))return authorization.substring(7);return Arrays.stream(Optional.ofNullable(req.getCookies()).orElse(new Cookie[0])).filter(c->c.getName().equals("bc_session")).map(Cookie::getValue).findFirst().orElse(null);}));
        return http.build();
    }
}
