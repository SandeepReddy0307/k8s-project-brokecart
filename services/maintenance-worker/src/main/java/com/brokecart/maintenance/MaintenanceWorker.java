package com.brokecart.maintenance;
import java.net.URI;
import java.net.http.*;
import java.time.Duration;
/** A bounded application task suitable for a Job/CronJob. No infrastructure setup. */
public class MaintenanceWorker {
    public static void main(String[] args)throws Exception{
        String task=System.getenv("TASK"),token=System.getenv("INTERNAL_TOKEN");if(token==null||token.length()<32)throw new IllegalArgumentException("INTERNAL_TOKEN is required");
        String base,path;
        if("expire-reservations".equals(task)){base=System.getenv("INVENTORY_URL");path="/internal/inventory/expire";}
        else if("reconcile-payments".equals(task)){base=System.getenv("PAYMENTS_URL");path="/internal/payments/reconcile";}
        else throw new IllegalArgumentException("TASK must be expire-reservations or reconcile-payments");
        if(base==null)throw new IllegalArgumentException("Task service URL is required");
        var request=HttpRequest.newBuilder(URI.create(base+path)).timeout(Duration.ofSeconds(30)).header("X-Internal-Token",token).header("Content-Type","application/json").POST(HttpRequest.BodyPublishers.ofString("{}")).build();
        var response=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build().send(request,HttpResponse.BodyHandlers.ofString());
        if(response.statusCode()/100!=2)throw new IllegalStateException("Maintenance task failed with HTTP "+response.statusCode());System.out.println("Completed "+task+": "+response.body());
    }
}
