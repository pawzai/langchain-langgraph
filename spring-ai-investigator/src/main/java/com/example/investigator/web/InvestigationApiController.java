package com.example.investigator.web;

import com.example.investigator.domain.ApprovalRequest;
import com.example.investigator.domain.InvestigateRequest;
import com.example.investigator.domain.InvestigationResult;
import com.example.investigator.service.HealthCheckService;
import com.example.investigator.service.InvestigationService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** JSON API, so the workflow can be driven from a script as well as the browser. */
@RestController
@RequestMapping("/api")
public class InvestigationApiController {

    private final InvestigationService investigationService;
    private final HealthCheckService healthCheckService;

    public InvestigationApiController(InvestigationService investigationService,
                                      HealthCheckService healthCheckService) {
        this.investigationService = investigationService;
        this.healthCheckService = healthCheckService;
    }

    @PostMapping("/investigate")
    public InvestigationResult investigate(@RequestBody InvestigateRequest request) {
        return investigationService.investigate(request);
    }

    @PostMapping("/approve")
    public InvestigationResult approve(@RequestBody ApprovalRequest request) {
        return investigationService.resume(request);
    }

    @GetMapping("/health/checks")
    public ResponseEntity<HealthCheckService.Report> healthChecks() {
        HealthCheckService.Report report = healthCheckService.run();
        return report.healthy()
                ? ResponseEntity.ok(report)
                : ResponseEntity.status(503).body(report);
    }
}
