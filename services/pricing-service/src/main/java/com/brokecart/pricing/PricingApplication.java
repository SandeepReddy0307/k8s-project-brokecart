package com.brokecart.pricing;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication(scanBasePackages={"com.brokecart.pricing","com.brokecart.common"})
public class PricingApplication {
    public static void main(String[] args) { SpringApplication.run(PricingApplication.class, args); }
}
