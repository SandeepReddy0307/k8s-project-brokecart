package com.brokecart.shipping;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication(scanBasePackages={"com.brokecart.shipping","com.brokecart.common"})
public class ShippingApplication { public static void main(String[] args){SpringApplication.run(ShippingApplication.class,args);} }
