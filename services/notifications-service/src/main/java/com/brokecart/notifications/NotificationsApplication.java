package com.brokecart.notifications;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication(scanBasePackages={"com.brokecart.notifications","com.brokecart.common"})
public class NotificationsApplication { public static void main(String[] args){SpringApplication.run(NotificationsApplication.class,args);} }
