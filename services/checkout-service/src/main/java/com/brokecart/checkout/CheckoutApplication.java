package com.brokecart.checkout;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication(scanBasePackages={"com.brokecart.checkout","com.brokecart.common"})
public class CheckoutApplication { public static void main(String[] args){SpringApplication.run(CheckoutApplication.class,args);} }
