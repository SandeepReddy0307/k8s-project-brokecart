package com.brokecart.identity;
import com.brokecart.common.Store;
import com.brokecart.common.Security;
import com.nimbusds.jose.jwk.*;
import com.nimbusds.jose.jwk.source.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.interfaces.*;
import java.security.spec.*;
import java.time.Instant;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.env.Environment;
import org.springframework.http.*;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.oauth2.jose.jws.*;
import org.springframework.security.oauth2.jwt.*;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import static com.brokecart.common.Data.*;
@RestController
public class IdentityController {
    private final Store store; private final BCryptPasswordEncoder passwords=new BCryptPasswordEncoder(12);
    private final JwtEncoder encoder;private final JwsHeader header;private final boolean secure;
    private final String dummyHash=passwords.encode("not-a-real-account-password");
    public record Credentials(@NotBlank @Email @Size(max=254) String email,@NotNull @Size(min=12,max=128) String password){}
    public IdentityController(Store store,Environment environment,@Value("${app.jwt-public-key:}") String pub,@Value("${app.jwt-private-key:}") String priv,@Value("${app.cookie-secure:true}") boolean secure)throws Exception{
        this.store=store;this.secure=secure;
        if(Arrays.asList(environment.getActiveProfiles()).contains("local")){encoder=new NimbusJwtEncoder(new ImmutableSecret<>(Security.LOCAL_KEY.getBytes(StandardCharsets.UTF_8)));header=JwsHeader.with(MacAlgorithm.HS256).build();}
        else {var factory=KeyFactory.getInstance("RSA");var publicKey=(RSAPublicKey)factory.generatePublic(new X509EncodedKeySpec(pem(pub,"PUBLIC KEY")));var privateKey=(RSAPrivateKey)factory.generatePrivate(new PKCS8EncodedKeySpec(pem(priv,"PRIVATE KEY")));encoder=new NimbusJwtEncoder(new ImmutableJWKSet<>(new JWKSet(new com.nimbusds.jose.jwk.RSAKey.Builder(publicKey).privateKey(privateKey).keyID("brokecart-v1").build())));header=JwsHeader.with(SignatureAlgorithm.RS256).build();}
    }
    private static byte[] pem(String value,String kind){return Base64.getDecoder().decode(value.replace("-----BEGIN "+kind+"-----","").replace("-----END "+kind+"-----","").replaceAll("\\s",""));}
    private String accountKey(String email){return "account:"+email.strip().toLowerCase(Locale.ROOT);}
    private Map<String,Object> publicUser(Map<String,Object> user){return map("id",text(user,"id"),"email",text(user,"email"),"roles",user.get("roles"));}
    @PostMapping("/api/identity/register") @Transactional
    public ResponseEntity<?> register(@Valid @RequestBody Credentials request){create(request,List.of("CUSTOMER"));return ResponseEntity.status(201).body(map("message","Registration processed. You can now sign in."));}
    private Map<String,Object> create(Credentials request,List<String> roles){String key=accountKey(request.email());var prior=store.lock(key);if(prior!=null)return prior;var user=map("id",UUID.randomUUID().toString(),"email",request.email().strip().toLowerCase(Locale.ROOT),"passwordHash",passwords.encode(request.password()),"roles",roles);store.save(key,user);return user;}
    @PostMapping("/internal/identity/operators") @Transactional
    public Map<String,Object> operator(@Valid @RequestBody Credentials request){var user=create(request,List.of("CUSTOMER","OPERATOR"));user.put("roles",List.of("CUSTOMER","OPERATOR"));store.save(accountKey(request.email()),user);return publicUser(user);}
    @PostMapping("/api/identity/login") @Transactional
    public ResponseEntity<?> login(@Valid @RequestBody Credentials request){
        String key=accountKey(request.email());String attemptsKey="attempt:"+request.email().strip().toLowerCase(Locale.ROOT);var attempts=store.lock(attemptsKey);
        if(attempts!=null&&number(attempts,"blockedUntil")>Instant.now().getEpochSecond())return ResponseEntity.status(429).body(map("detail","Too many attempts; try again in five minutes"));
        var user=store.find(key);boolean valid=passwords.matches(request.password(),user==null?dummyHash:text(user,"passwordHash"));
        if(user==null||!valid){long failures=attempts==null?1:number(attempts,"failures")+1;store.save(attemptsKey,map("failures",failures,"blockedUntil",failures>=5?Instant.now().plusSeconds(300).getEpochSecond():0));return ResponseEntity.status(401).body(map("detail","Invalid email or password"));}
        store.delete(attemptsKey);Instant now=Instant.now();var claims=JwtClaimsSet.builder().issuer("brokecart-identity").subject(text(user,"id")).audience(List.of("brokecart")).issuedAt(now).expiresAt(now.plusSeconds(3600)).id(UUID.randomUUID().toString()).claim("email",text(user,"email")).claim("roles",user.get("roles")).build();
        String token=encoder.encode(JwtEncoderParameters.from(header,claims)).getTokenValue();
        var cookie=ResponseCookie.from("bc_session",token).httpOnly(true).secure(secure).sameSite("Strict").path("/").maxAge(3600).build();
        return ResponseEntity.ok().header(HttpHeaders.SET_COOKIE,cookie.toString()).body(map("user",publicUser(user)));
    }
    @GetMapping("/api/identity/me") public Object me(@AuthenticationPrincipal Jwt jwt){return map("user",map("id",jwt.getSubject(),"email",jwt.getClaimAsString("email"),"roles",jwt.getClaimAsStringList("roles")));}
    @PostMapping("/api/identity/logout") public ResponseEntity<?> logout(){return ResponseEntity.noContent().header(HttpHeaders.SET_COOKIE,ResponseCookie.from("bc_session","").httpOnly(true).secure(secure).sameSite("Strict").path("/").maxAge(0).build().toString()).build();}
}
