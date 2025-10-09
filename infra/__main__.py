"""Pulumi infrastructure for IT Indaba 2025 WhatsApp Challenge."""

import pulumi
import pulumi_gcp as gcp

# Get configuration
config = pulumi.Config()
gcp_config = pulumi.Config("gcp")
project = gcp_config.require("project")
region = gcp_config.get("region") or "us-central1"

# Enable required APIs
apis_to_enable = [
    "compute.googleapis.com",
    "run.googleapis.com",
    "redis.googleapis.com",
    "secretmanager.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com",
    "cloudbuild.googleapis.com",
    "containerregistry.googleapis.com",
    "cloudscheduler.googleapis.com",
]

enabled_apis = []
for api in apis_to_enable:
    service = gcp.projects.Service(
        f"enable-{api.replace('.', '-')}",
        service=api,
        project=project,
        disable_on_destroy=False,
    )
    enabled_apis.append(service)

# Create VPC Network
vpc_network = gcp.compute.Network(
    "it-indaba-vpc",
    name="it-indaba-vpc",
    auto_create_subnetworks=False,
    description="VPC for IT Indaba 2025 Challenge",
    opts=pulumi.ResourceOptions(depends_on=enabled_apis)
)

# Create subnet
subnet = gcp.compute.Subnetwork(
    "it-indaba-subnet",
    name="it-indaba-subnet",
    ip_cidr_range="10.0.0.0/24",
    region=region,
    network=vpc_network.id,
    private_ip_google_access=True,
)

# Reserve IP range for VPC peering (required for Memorystore)
private_ip_range = gcp.compute.GlobalAddress(
    "redis-private-ip",
    name="redis-private-ip-range",
    purpose="VPC_PEERING",
    address_type="INTERNAL",
    prefix_length=16,
    network=vpc_network.id,
)

# Create VPC peering connection for Memorystore
private_vpc_connection = gcp.servicenetworking.Connection(
    "redis-vpc-connection",
    network=vpc_network.id,
    service="servicenetworking.googleapis.com",
    reserved_peering_ranges=[private_ip_range.name],
)

# Create Memorystore Redis instance
redis_instance = gcp.redis.Instance(
    "it-indaba-redis",
    name="it-indaba-redis",
    tier="BASIC",
    memory_size_gb=1,
    region=region,
    authorized_network=vpc_network.id,
    redis_version="REDIS_7_0",
    display_name="IT Indaba 2025 Challenge Redis",
    opts=pulumi.ResourceOptions(depends_on=[private_vpc_connection])
)

# Create Serverless VPC Access Connector (for Cloud Run to access Redis)
vpc_connector = gcp.vpcaccess.Connector(
    "it-indaba-vpc-connector",
    name="it-indaba-connector",
    region=region,
    network=vpc_network.name,
    ip_cidr_range="10.8.0.0/28",
    min_throughput=200,
    max_throughput=300,
    opts=pulumi.ResourceOptions(depends_on=[subnet])
)

# Create Service Account for Cloud Run
service_account = gcp.serviceaccount.Account(
    "cloudrun-sa",
    account_id="it-indaba-cloudrun-sa",
    display_name="IT Indaba Cloud Run Service Account",
)

# Grant Secret Manager access to Service Account
secret_accessor_binding = gcp.projects.IAMMember(
    "sa-secret-accessor",
    project=project,
    role="roles/secretmanager.secretAccessor",
    member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Get project number for Cloud Build service account
project_info = gcp.organizations.get_project()

# Grant Cloud Build service account permissions to deploy to Cloud Run
cloudbuild_run_admin = gcp.projects.IAMMember(
    "cloudbuild-run-admin",
    project=project,
    role="roles/run.admin",
    member=f"serviceAccount:{project_info.number}@cloudbuild.gserviceaccount.com",
    opts=pulumi.ResourceOptions(depends_on=enabled_apis)
)

cloudbuild_sa_user = gcp.projects.IAMMember(
    "cloudbuild-sa-user",
    project=project,
    role="roles/iam.serviceAccountUser",
    member=f"serviceAccount:{project_info.number}@cloudbuild.gserviceaccount.com",
    opts=pulumi.ResourceOptions(depends_on=enabled_apis)
)

# Grant Cloud Build access to Storage (for GCR)
cloudbuild_storage_admin = gcp.projects.IAMMember(
    "cloudbuild-storage-admin",
    project=project,
    role="roles/storage.admin",
    member=f"serviceAccount:{project_info.number}@cloudbuild.gserviceaccount.com",
    opts=pulumi.ResourceOptions(depends_on=enabled_apis)
)

# Create Secret Manager secrets (placeholders - actual values set via CLI or console)
whatsapp_token_secret = gcp.secretmanager.Secret(
    "whatsapp-api-token",
    secret_id="whatsapp-api-token",
    replication=gcp.secretmanager.SecretReplicationArgs(
        auto=gcp.secretmanager.SecretReplicationAutoArgs(),
    ),
)

whatsapp_phone_id_secret = gcp.secretmanager.Secret(
    "whatsapp-phone-number-id",
    secret_id="whatsapp-phone-number-id",
    replication=gcp.secretmanager.SecretReplicationArgs(
        auto=gcp.secretmanager.SecretReplicationAutoArgs(),
    ),
)

whatsapp_verify_token_secret = gcp.secretmanager.Secret(
    "whatsapp-verify-token",
    secret_id="whatsapp-verify-token",
    replication=gcp.secretmanager.SecretReplicationArgs(
        auto=gcp.secretmanager.SecretReplicationAutoArgs(),
    ),
)

posthog_api_key_secret = gcp.secretmanager.Secret(
    "posthog-api-key",
    secret_id="posthog-api-key",
    replication=gcp.secretmanager.SecretReplicationArgs(
        auto=gcp.secretmanager.SecretReplicationAutoArgs(),
    ),
)

# NOTE: Secret versions are NOT managed by Pulumi
# This keeps secret values out of Pulumi state and only in GCP Secret Manager
# Add secret values after deployment using:
# echo -n 'YOUR_VALUE' | gcloud secrets versions add SECRET_NAME --data-file=-

# Build and push Docker image using Cloud Build (not local Docker)
# Cloud Build will handle building and pushing to GCR
# Run: gcloud builds submit --config cloudbuild.yaml

# Reference the image location
image_name = f"gcr.io/{project}/it-indaba-chatbot:latest"

# Create Cloud Run service
cloudrun_service = gcp.cloudrunv2.Service(
    "it-indaba-chatbot",
    name="it-indaba-chatbot",
    location=region,
    ingress="INGRESS_TRAFFIC_ALL",
    template=gcp.cloudrunv2.ServiceTemplateArgs(
        service_account=service_account.email,
        vpc_access=gcp.cloudrunv2.ServiceTemplateVpcAccessArgs(
            connector=vpc_connector.id,
            egress="PRIVATE_RANGES_ONLY",
        ),
        scaling=gcp.cloudrunv2.ServiceTemplateScalingArgs(
            min_instance_count=0,
            max_instance_count=10,
        ),
        containers=[
            gcp.cloudrunv2.ServiceTemplateContainerArgs(
                image=image_name,
                ports=[gcp.cloudrunv2.ServiceTemplateContainerPortArgs(
                    container_port=8080,
                )],
                resources=gcp.cloudrunv2.ServiceTemplateContainerResourcesArgs(
                    limits={
                        "cpu": "1",
                        "memory": "512Mi",
                    },
                ),
                envs=[
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="GCP_PROJECT_ID",
                        value=project,
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="REDIS_HOST",
                        value=redis_instance.host,
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="REDIS_PORT",
                        value="6379",
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="WHATSAPP_API_TOKEN",
                        value_source=gcp.cloudrunv2.ServiceTemplateContainerEnvValueSourceArgs(
                            secret_key_ref=gcp.cloudrunv2.ServiceTemplateContainerEnvValueSourceSecretKeyRefArgs(
                                secret=whatsapp_token_secret.secret_id,
                                version="latest",
                            ),
                        ),
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="WHATSAPP_PHONE_NUMBER_ID",
                        value_source=gcp.cloudrunv2.ServiceTemplateContainerEnvValueSourceArgs(
                            secret_key_ref=gcp.cloudrunv2.ServiceTemplateContainerEnvValueSourceSecretKeyRefArgs(
                                secret=whatsapp_phone_id_secret.secret_id,
                                version="latest",
                            ),
                        ),
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="WHATSAPP_VERIFY_TOKEN",
                        value_source=gcp.cloudrunv2.ServiceTemplateContainerEnvValueSourceArgs(
                            secret_key_ref=gcp.cloudrunv2.ServiceTemplateContainerEnvValueSourceSecretKeyRefArgs(
                                secret=whatsapp_verify_token_secret.secret_id,
                                version="latest",
                            ),
                        ),
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="POSTHOG_API_KEY",
                        value_source=gcp.cloudrunv2.ServiceTemplateContainerEnvValueSourceArgs(
                            secret_key_ref=gcp.cloudrunv2.ServiceTemplateContainerEnvValueSourceSecretKeyRefArgs(
                                secret=posthog_api_key_secret.secret_id,
                                version="latest",
                            ),
                        ),
                    ),
                    gcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="POSTHOG_HOST",
                        value="https://eu.i.posthog.com",
                    ),
                ],
            ),
        ],
    ),
    opts=pulumi.ResourceOptions(depends_on=[
        vpc_connector,
        redis_instance,
        whatsapp_token_secret,
        whatsapp_phone_id_secret,
        whatsapp_verify_token_secret,
        posthog_api_key_secret,
        secret_accessor_binding,
    ])
)

# Allow unauthenticated access to Cloud Run
cloudrun_iam_member = gcp.cloudrunv2.ServiceIamMember(
    "cloudrun-invoker",
    name=cloudrun_service.name,
    location=region,
    role="roles/run.invoker",
    member="allUsers",
)

# Create Cloud Scheduler job for session inactivity warnings
# This job runs every minute to check for inactive users
scheduler_job = gcp.cloudscheduler.Job(
    "session-checker",
    name="session-inactivity-checker",
    description="Check for inactive users and send 2-minute warnings",
    schedule="* * * * *",  # Every minute (standard cron format)
    time_zone="Africa/Johannesburg",
    attempt_deadline="60s",
    http_target=gcp.cloudscheduler.JobHttpTargetArgs(
        http_method="POST",
        uri=pulumi.Output.concat(cloudrun_service.uri, "/check-sessions"),
        oidc_token=gcp.cloudscheduler.JobHttpTargetOidcTokenArgs(
            service_account_email=service_account.email,
        ),
    ),
    opts=pulumi.ResourceOptions(depends_on=[cloudrun_service, service_account])
)

# Grant Cloud Scheduler permission to invoke Cloud Run
scheduler_invoker = gcp.cloudrunv2.ServiceIamMember(
    "scheduler-invoker",
    name=cloudrun_service.name,
    location=region,
    role="roles/run.invoker",
    member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Export outputs
pulumi.export("vpc_network_name", vpc_network.name)
pulumi.export("vpc_network_id", vpc_network.id)
pulumi.export("redis_host", redis_instance.host)
pulumi.export("redis_port", redis_instance.port)
pulumi.export("redis_connection", pulumi.Output.all(redis_instance.host, redis_instance.port).apply(lambda args: f"{args[0]}:{args[1]}"))
pulumi.export("cloudrun_url", cloudrun_service.uri)
pulumi.export("webhook_url", pulumi.Output.concat(cloudrun_service.uri, "/webhook"))
pulumi.export("service_account_email", service_account.email)
pulumi.export("vpc_connector_name", vpc_connector.name)

# Export instructions
pulumi.export("instructions", pulumi.Output.concat(
    "\n\n=== SETUP INSTRUCTIONS ===\n\n",
    "1. Add WhatsApp secrets (REQUIRED - Cloud Run won't start without these):\n",
    f"   echo -n 'YOUR_WHATSAPP_TOKEN' | gcloud secrets versions add whatsapp-api-token --data-file=- --project={project}\n",
    f"   echo -n 'YOUR_PHONE_NUMBER_ID' | gcloud secrets versions add whatsapp-phone-number-id --data-file=- --project={project}\n",
    f"   echo -n 'challenge_token_2025' | gcloud secrets versions add whatsapp-verify-token --data-file=- --project={project}\n\n",
    "2. Build and deploy with Cloud Build:\n",
    f"   gcloud builds submit --config cloudbuild.yaml --project={project}\n\n",
    "3. Configure WhatsApp webhook:\n",
    "   URL: ", cloudrun_service.uri, "/webhook\n",
    "   Verify Token: challenge_token_2025\n\n",
    "4. Test the health endpoint:\n",
    "   curl ", cloudrun_service.uri, "/health\n\n",
    "5. (Optional) Set up automated builds:\n",
    f"   gcloud builds triggers create github --repo-name=jem-it-indaba-chatbot --repo-owner=Jem-HR --branch-pattern=^main$ --build-config=cloudbuild.yaml --project={project}\n"
))
