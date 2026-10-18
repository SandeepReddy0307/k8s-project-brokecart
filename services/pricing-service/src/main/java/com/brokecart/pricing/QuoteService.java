package com.brokecart.pricing;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.time.Instant;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
@Service
public class QuoteService {
    public record Item(@NotBlank @Pattern(regexp="bc-[0-9]{3}") String productId, @Min(1) @Max(10) int quantity) {}
    public record Request(@NotEmpty @Size(max=30) List<@NotNull @Valid Item> items, @Size(max=30) String promoCode) {}
    public record Line(String productId, String name, int quantity, long unitPriceCents, long totalCents, long productVersion) {}
    public record Quote(String quoteId, String currency, List<Line> lines, long subtotalCents, long discountCents,
                        long shippingCents, long totalCents, String promoCode, Instant expiresAt) {}
    private final CatalogClient catalog;
    QuoteService(CatalogClient catalog) { this.catalog = catalog; }
    public Quote quote(Request request) {
        String promo = request.promoCode() == null ? "" : request.promoCode().strip().toUpperCase(Locale.ROOT);
        if (!promo.isEmpty() && !promo.equals("BROKE10"))
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY, "Promotion code is not valid");
        Set<String> seen = new HashSet<>();
        List<Line> lines = new ArrayList<>();
        long subtotal = 0;
        for (Item item : request.items()) {
            if (!seen.add(item.productId())) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Duplicate product; combine quantities");
            var product = catalog.product(item.productId());
            long total = Math.multiplyExact(product.priceCents(), item.quantity());
            subtotal = Math.addExact(subtotal, total);
            lines.add(new Line(product.id(), product.name(), item.quantity(), product.priceCents(), total, product.version()));
        }
        long discount = promo.equals("BROKE10") ? subtotal / 10 : 0;
        long shipping = subtotal - discount >= 10000 ? 0 : 499;
        return new Quote(UUID.randomUUID().toString(), "USD", List.copyOf(lines), subtotal, discount, shipping,
                subtotal - discount + shipping, promo, Instant.now().plusSeconds(300));
    }
}
