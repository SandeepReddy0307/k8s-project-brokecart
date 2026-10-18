package com.brokecart.pricing;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
@SpringBootTest @AutoConfigureMockMvc @ActiveProfiles("local")
class PricingApiTest {
    @Autowired MockMvc mvc;
    @Test void validatesBeforeCallingCatalog() throws Exception {
        for (String body : new String[]{"{\"items\":[]}", "{\"items\":[null]}", "{\"items\":[{\"productId\":\"bc-001\",\"quantity\":0}]}", "{\"items\":[{\"productId\":\"../secret\",\"quantity\":1}]}"})
            mvc.perform(post("/api/pricing/quotes").contentType("application/json").content(body)).andExpect(status().isBadRequest());
    }
}
