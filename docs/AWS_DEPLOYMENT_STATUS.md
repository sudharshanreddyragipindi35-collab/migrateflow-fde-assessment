# AWS assessment deployment

Deployment date: 20 September 2026. This is a single-host assessment environment, not a production service.

## Address and infrastructure

- Demo: https://demo-migrateflow.51-21-247-103.sslip.io
- Region: eu-north-1 (Stockholm)
- EC2: i-0bf0ffacaa7e7d19c, m7i-flex.large, Amazon Linux 2023, 2 vCPU / 8 GiB RAM
- EBS root volume: vol-0b2bc589290ac138a, expanded from 8 GiB to 30 GiB; partition and XFS expanded successfully. Existing volume is unencrypted; resizing did not add encryption. Use synthetic data only.
- Server application directory: /home/ec2-user/migrateflow
- Stack: docker-compose.aws.yml; Caddy HTTPS -> Nginx routing -> React static UI / FastAPI backend; internal Ollama qwen2.5:7b-instruct.
- Persistent named volumes hold database, uploads, model and certificates. Backend/Ollama ports are not published. Only HTTP/HTTPS are public; internal edge is bound to loopback.

The free sslip.io hostname resolves from its embedded IPv4 address. It depends on that DNS provider and this server retaining its current public IP. A stop/start can change the IP and break this URL. Arrange a stable address before any planned stop/start during evaluation. No paid domain or load balancer was created.

## Configuration and credentials

The server .env contains only PUBLIC_ORIGIN and DEMO_HOST. No AWS access keys or model keys were uploaded. Local Ollama needs no key; Anthropic is disabled. Model inference is serialized, capped in code and allowed a 180-second request timeout for this CPU host. Fallback remains explicit and subject to human review.

The initial 60-second live-model smoke fell back and was correctly reported as a failure. A hosted UI walkthrough passed: upload, two escalations resolved through UI controls, automatic delivery of one corrected synthetic record, and UI undo, with no page JavaScript errors. Evidence is in evaluation/aws_ui_report.json. Final live Ollama smoke passed in 123.50 seconds with seven proposals, validation, delivery and undo; see evaluation/aws_live_model_report.json. Initial source GitHub Actions checks also passed.

## Operation

From the server application directory:

```sh
sudo docker compose -f docker-compose.aws.yml ps -a
sudo docker compose -f docker-compose.aws.yml logs --tail 100 backend
sudo docker compose -f docker-compose.aws.yml up -d --build
```

The repository is private. Source was transferred as a clean archive without credentials, local databases or uploads; no GitHub token was installed on EC2. Do not copy your local .env into deployment archives. Schema initialization is the prototype SQLite bootstrap, not a production migration system.

## Budget and availability

At the console's displayed compute rate of $0.10175/hour, compute is about $2.44/day. With a public IPv4 address and estimated 30 GiB gp3 storage, allow roughly $2.65/day before additional usage, taxes or credits. The earlier $59.68 credit balance is shared across the AWS account, not reserved for this instance. Other retained volumes/resources consume it too. Keep the AWS Free plan and check the actual remaining credit balance daily during the review window.

Stopping compute interrupts reviewer access and does not stop EBS charges. Do not delete named volumes or terminate the instance until the assessment is finished and any required data is exported. Budget alerts do not guarantee a hard spending cap.

## Submission

Source: https://github.com/sudharshanreddyragipindi35-collab/migrateflow-fde-assessment (private; grant panel access). The original workspace origin remains unchanged. docs/APPROACH_ONE_PAGE.html was visually verified to fit one A4 page. No video is planned for the hosted-link submission route.
