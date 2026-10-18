package com.brokecart.pricing;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
class QuoteServiceTest {
    CatalogClient catalog = mock(CatalogClient.class);
    QuoteService service = new QuoteService(catalog);
    @Test void usesAuthoritativePricesAndRoundsDiscountDown() {
        when(catalog.product("bc-001")).thenReturn(new CatalogClient.Product("bc-001", "Headphones", 8990, "USD", 3));
        var quote = service.quote(new QuoteService.Request(List.of(new QuoteService.Item("bc-001", 1)), "broke10"));
        assertEquals(8990, quote.subtotalCents()); assertEquals(899, quote.discountCents());
        assertEquals(499, quote.shippingCents()); assertEquals(8590, quote.totalCents());
        assertEquals(3, quote.lines().get(0).productVersion());
    }
    @Test void freeShippingDependsOnDiscountedSubtotal() {
        when(catalog.product("bc-001")).thenReturn(new CatalogClient.Product("bc-001", "Headphones", 5000, "USD", 1));
        assertEquals(0, service.quote(new QuoteService.Request(List.of(new QuoteService.Item("bc-001", 2)), "")).shippingCents());
        assertEquals(499, service.quote(new QuoteService.Request(List.of(new QuoteService.Item("bc-001", 2)), "BROKE10")).shippingCents());
    }
    @Test void rejectsUnknownPromotionsAndDuplicateLines() {
        assertThrows(ResponseStatusException.class, () -> service.quote(new QuoteService.Request(List.of(new QuoteService.Item("bc-001", 1)), "fake")));
        verifyNoInteractions(catalog);
        when(catalog.product("bc-001")).thenReturn(new CatalogClient.Product("bc-001", "Headphones", 5000, "USD", 1));
        assertThrows(ResponseStatusException.class, () -> service.quote(new QuoteService.Request(List.of(new QuoteService.Item("bc-001", 1), new QuoteService.Item("bc-001", 2)), "")));
    }
}
