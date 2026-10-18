package com.brokecart.catalog;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication(scanBasePackages={"com.brokecart.catalog","com.brokecart.common"})
public class CatalogApplication {
    public static void main(String[] args) { SpringApplication.run(CatalogApplication.class, args); }
}
