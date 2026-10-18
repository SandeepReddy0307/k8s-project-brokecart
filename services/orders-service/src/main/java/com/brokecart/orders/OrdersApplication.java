package com.brokecart.orders;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication(scanBasePackages={"com.brokecart.orders","com.brokecart.common"})
public class OrdersApplication { public static void main(String[] args){SpringApplication.run(OrdersApplication.class,args);} }
