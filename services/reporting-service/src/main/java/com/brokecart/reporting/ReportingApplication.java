package com.brokecart.reporting;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication(scanBasePackages={"com.brokecart.reporting","com.brokecart.common"})
public class ReportingApplication { public static void main(String[] args){SpringApplication.run(ReportingApplication.class,args);} }
