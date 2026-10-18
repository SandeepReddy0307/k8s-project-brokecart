package com.brokecart.catalog;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("local")
class CatalogApiTest {
    @Autowired MockMvc mvc;
    @Test void seedsAndPaginatesRealDatabase() throws Exception {
        mvc.perform(get("/api/catalog/products").param("size", "2"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.total").value(8))
            .andExpect(jsonPath("$.items.length()").value(2));
    }
    @Test void filtersAndRejectsInvalidRequests() throws Exception {
        mvc.perform(get("/api/catalog/products").param("category", "Tech").param("q", "CLOUD"))
            .andExpect(jsonPath("$.total").value(1)).andExpect(jsonPath("$.items[0].priceCents").value(8990));
        mvc.perform(get("/api/catalog/products").param("size", "0")).andExpect(status().isBadRequest());
        mvc.perform(get("/api/catalog/products/nope")).andExpect(status().isNotFound());
    }
    @Test void readinessIncludesDatabase() throws Exception {
        mvc.perform(get("/actuator/health/readiness")).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("UP"));
    }
}
