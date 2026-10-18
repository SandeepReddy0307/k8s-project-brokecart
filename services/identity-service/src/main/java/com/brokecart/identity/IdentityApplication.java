package com.brokecart.identity;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication(scanBasePackages={"com.brokecart.identity","com.brokecart.common"})
public class IdentityApplication { public static void main(String[] args){SpringApplication.run(IdentityApplication.class,args);} }
