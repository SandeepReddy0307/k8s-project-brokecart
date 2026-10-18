package com.brokecart.common;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
@RestControllerAdvice
public class Errors {
    @ExceptionHandler(DataIntegrityViolationException.class)
    public ProblemDetail conflict(DataIntegrityViolationException e){return ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT,"Concurrent or duplicate operation; retry with the same idempotency key");}
    @ExceptionHandler(IllegalArgumentException.class)
    public ProblemDetail invalid(IllegalArgumentException e){return ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST,"Invalid request");}
}
