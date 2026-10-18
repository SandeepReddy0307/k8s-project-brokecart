package com.brokecart.paymentprovider;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication(scanBasePackages={"com.brokecart.paymentprovider","com.brokecart.common"})
public class PaymentProviderApplication { public static void main(String[] args){SpringApplication.run(PaymentProviderApplication.class,args);} }
