package com.brokecart.inventory;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication(scanBasePackages={"com.brokecart.inventory","com.brokecart.common"})
public class InventoryApplication { public static void main(String[] args){SpringApplication.run(InventoryApplication.class,args);} }
