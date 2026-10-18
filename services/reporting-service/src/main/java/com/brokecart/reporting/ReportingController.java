package com.brokecart.reporting;
import com.brokecart.common.*;
import java.util.*;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import static com.brokecart.common.Data.*;
@RestController
public class ReportingController implements EventHandler {
    private final Store store;
    public ReportingController(Store store){this.store=store;}
    @Override public void handle(Event event){if(event.eventType().startsWith("order."))store.save("projection:"+event.aggregateId(),map("orderId",event.aggregateId(),"status",text(event.payload(),"status"),"totalCents",number(event.payload(),"totalCents"),"createdAt",text(event.payload(),"createdAt")));}
    @GetMapping("/api/operations/reports") @PreAuthorize("hasRole('OPERATOR')") public Object report(){var orders=store.all("projection:");var byStatus=new TreeMap<String,Long>();long gross=0,refunded=0;for(var order:orders){String state=text(order,"status");byStatus.merge(state,1L,Long::sum);if(Set.of("CONFIRMED","SHIPPED","DELIVERED").contains(state))gross+=number(order,"totalCents");if(Set.of("CANCELLED","RETURNED").contains(state))refunded+=number(order,"totalCents");}return map("currency","USD","orders",orders.size(),"byStatus",byStatus,"netSalesCents",gross,"refundedCents",refunded);}
}
