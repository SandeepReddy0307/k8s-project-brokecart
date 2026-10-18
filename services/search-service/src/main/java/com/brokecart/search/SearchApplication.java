package com.brokecart.search;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication(scanBasePackages={"com.brokecart.search","com.brokecart.common"})
public class SearchApplication { public static void main(String[] args){SpringApplication.run(SearchApplication.class,args);} }
