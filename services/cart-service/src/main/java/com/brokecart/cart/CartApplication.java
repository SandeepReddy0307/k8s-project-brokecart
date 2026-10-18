package com.brokecart.cart;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication(scanBasePackages={"com.brokecart.cart","com.brokecart.common"})
public class CartApplication { public static void main(String[] args){SpringApplication.run(CartApplication.class,args);} }
