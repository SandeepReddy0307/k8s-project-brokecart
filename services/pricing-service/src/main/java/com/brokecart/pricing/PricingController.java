package com.brokecart.pricing;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping("/api/pricing")
public class PricingController {
    private final QuoteService service;
    PricingController(QuoteService service) { this.service = service; }
    @PostMapping("/quotes")
    public QuoteService.Quote quote(@Valid @RequestBody QuoteService.Request request) { return service.quote(request); }
}
