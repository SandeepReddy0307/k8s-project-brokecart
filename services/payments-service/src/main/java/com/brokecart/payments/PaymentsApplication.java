package com.brokecart.payments;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication(scanBasePackages={"com.brokecart.payments","com.brokecart.common"})
public class PaymentsApplication { public static void main(String[] args){SpringApplication.run(PaymentsApplication.class,args);} }
