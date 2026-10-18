package com.brokecart.catalog;
import java.util.List;
import java.util.Locale;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
@RestController
@RequestMapping("/api/catalog")
public class CatalogController {
    private final ProductRepository repository;
    CatalogController(ProductRepository repository) { this.repository = repository; }
    public record Products(List<Product> items, long total, int page, int size) {}
    @GetMapping("/products")
    public Products products(@RequestParam(defaultValue = "") String category,
                             @RequestParam(defaultValue = "") String q,
                             @RequestParam(defaultValue = "0") int page,
                             @RequestParam(defaultValue = "24") int size) {
        if (q.length() > 100 || category.length() > 40 || page < 0 || page > 10000 || size < 1 || size > 100)
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid catalog filter or pagination");
        var result = repository.browse(category.strip(), q.strip().toLowerCase(Locale.ROOT),
                PageRequest.of(page, size, Sort.by("id")));
        return new Products(result.getContent(), result.getTotalElements(), page, size);
    }
    @GetMapping("/products/{id}")
    public Product product(@PathVariable String id) {
        return repository.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Product not found"));
    }
}
