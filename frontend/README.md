# Rosetta Zero Web Dashboard

Web-based frontend for monitoring and managing the Rosetta Zero legacy code modernization system.

## Features

- **Dashboard Overview**: View system stats, active workflows, and recent certificates
- **Artifact Management**: Upload legacy artifacts (COBOL, FORTRAN, binaries) and track processing
- **Workflow Monitoring**: Monitor modernization progress through 5 phases
- **Test Results**: View test execution results and discrepancy reports
- **Certificates**: View and download equivalence certificates
- **Compliance Reports**: Generate and download compliance reports for regulatory submission
- **System Health**: Monitor AWS service metrics and system health
- **CloudWatch Logs**: Access and search system logs

## Tech Stack

- **Frontend**: React 18 + TypeScript + Vite
- **Styling**: Tailwind CSS
- **Authentication**: AWS Amplify + Cognito
- **API**: AWS API Gateway + Lambda
- **State Management**: React Hooks
- **Charts**: Recharts
- **Icons**: Lucide React

## Prerequisites

- Node.js 18+ and npm
- AWS Account with Cognito User Pool configured
- API Gateway endpoint URL

## Installation

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Configure environment variables:
```bash
cp .env.example .env
```

Edit `.env` with your AWS configuration:
```env
VITE_AWS_REGION=us-east-1
VITE_USER_POOL_ID=your-user-pool-id
VITE_USER_POOL_CLIENT_ID=your-client-id
VITE_API_URL=https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod
```

## Development

Run the development server:
```bash
npm run dev
```

The app will be available at `http://localhost:3000`

## Building for Production

Build the production bundle:
```bash
npm run build
```

The built files will be in the `dist/` directory.

## Deployment

### Deploy to S3 + CloudFront

1. Build the production bundle:
```bash
npm run build
```

2. Deploy using AWS CDK (from project root):
```bash
cdk deploy DashboardStack
```

3. The CDK will output the CloudFront URL where the dashboard is hosted.

### Manual S3 Deployment

```bash
# Build
npm run build

# Upload to S3
aws s3 sync dist/ s3://your-frontend-bucket/ --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*"
```

## Project Structure

```
frontend/
├── src/
│   ├── api/              # API client and endpoints
│   │   ├── client.ts     # Axios client with auth
│   │   └── index.ts      # API functions
│   ├── components/       # Reusable components
│   │   └── Layout.tsx    # Main layout with sidebar
│   ├── pages/            # Page components
│   │   ├── Dashboard.tsx
│   │   ├── Artifacts.tsx
│   │   ├── Workflows.tsx
│   │   ├── Certificates.tsx
│   │   ├── Compliance.tsx
│   │   ├── SystemHealth.tsx
│   │   └── Logs.tsx
│   ├── types/            # TypeScript types
│   │   └── index.ts
│   ├── App.tsx           # Main app component
│   ├── main.tsx          # Entry point
│   └── index.css         # Global styles
├── public/               # Static assets
├── index.html            # HTML template
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

## Authentication

The dashboard uses AWS Cognito for authentication. Users must be created in the Cognito User Pool by an administrator.

### Creating Users

```bash
aws cognito-idp admin-create-user \
  --user-pool-id YOUR_USER_POOL_ID \
  --username user@example.com \
  --user-attributes Name=email,Value=user@example.com \
  --temporary-password TempPassword123!
```

## API Integration

The dashboard communicates with the backend through API Gateway. All requests include a JWT token from Cognito in the Authorization header.

### API Endpoints

- `GET /dashboard/stats` - Dashboard statistics
- `GET /artifacts` - List artifacts
- `POST /artifacts/upload` - Upload artifact
- `GET /artifacts/{id}` - Get artifact details
- `GET /workflows` - List workflows
- `GET /workflows/{id}` - Get workflow details
- `GET /workflows/{id}/tests` - Get test results
- `GET /certificates` - List certificates
- `GET /certificates/{id}` - Get certificate details
- `POST /certificates/{id}/verify` - Verify certificate signature
- `GET /compliance/reports` - List compliance reports
- `POST /compliance/reports` - Generate compliance report
- `GET /system/health` - System health metrics
- `GET /logs` - CloudWatch logs

## Security

- All communication uses HTTPS
- Authentication via AWS Cognito
- API requests require valid JWT tokens
- CORS configured for dashboard origin only
- S3 bucket has public access blocked
- CloudFront serves frontend with HTTPS only

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Accessibility

The dashboard aims for WCAG 2.1 AA compliance:
- Keyboard navigation support
- Screen reader compatible
- Sufficient color contrast
- Focus indicators
- Semantic HTML

## Troubleshooting

### Authentication Issues

If you can't log in:
1. Verify Cognito User Pool ID and Client ID in `.env`
2. Check that the user exists in Cognito
3. Ensure the user's email is verified
4. Check browser console for errors

### API Errors

If API calls fail:
1. Verify API Gateway URL in `.env`
2. Check that the API Gateway has CORS enabled
3. Verify the Cognito authorizer is configured
4. Check CloudWatch Logs for Lambda errors

### Build Errors

If the build fails:
1. Delete `node_modules` and `package-lock.json`
2. Run `npm install` again
3. Check Node.js version (18+ required)
4. Clear Vite cache: `rm -rf node_modules/.vite`

## License

Copyright © 2024 Rosetta Zero. All rights reserved.
