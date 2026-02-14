# Scaling Guide: Supporting Thousands of Concurrent Users

This guide explains how the application is configured to scale to thousands of concurrent users on Google Cloud Run.

## Current Configuration

### Cloud Run Autoscaling

- **Min Instances**: 2 (keeps instances warm to avoid cold starts)
- **Max Instances**: 100 (optimized for Pro tier with 200 DB connections)
- **Concurrency per Instance**: 100 requests
- **Total Capacity**: Up to 10,000 concurrent requests (100 instances × 100 concurrency)

### Database Connection Pool

- **Pool Size per Instance**: 20 base connections
- **Max Overflow**: 10 additional connections
- **Total per Instance**: 30 connections
- **Max Total Connections**: 3,000 client connections (100 instances × 30)
- **Actual DB Connections**: PgBouncer (Supabase Pooler) efficiently pools these to ~200 actual database connections (matches Pro tier limit)

### Resource Allocation

- **Memory**: 4Gi limit, 2Gi request per instance
- **CPU**: 4 vCPU limit, 2 vCPU request per instance
- **Timeout**: 300 seconds (5 minutes) for long-running LLM requests

## Scaling Capacity Calculations

### Current Setup (Optimized for Pro Tier)

```
Max Concurrent Users = Max Instances × Concurrency per Instance
                    = 100 × 100
                    = 10,000 concurrent requests
```

### Database Connection Math (Pro Tier)

```
Client Connections = Instances × Connections per Instance
                   = 100 × 30
                   = 3,000 client connections

Actual DB Connections = Pooled by PgBouncer
                      = ~200 (matches Pro tier limit)
                      
At Peak Load:
- Each instance uses ~2-3 actual DB connections
- 100 instances × 2 DB connections = ~200 DB connections
- PgBouncer transaction pooling handles this efficiently
```

**Why this works**: PgBouncer uses transaction pooling, where many client connections share fewer actual database connections. This is safe because:
- Most requests are short-lived
- Connections are returned to the pool quickly
- PgBouncer manages the actual DB connection pool efficiently

## Scaling to Higher Loads

### Option 1: Increase Concurrency per Instance

**For**: Applications with fast, stateless requests

```yaml
containerConcurrency: 250  # Up from 100
DB_POOL_SIZE: "40"         # Increase proportionally
DB_MAX_OVERFLOW: "20"
```

**Capacity**: 100 instances × 250 = **25,000 concurrent requests** (requires Team tier for DB connections)

### Option 2: Increase Max Instances

**For**: Applications needing more total capacity

```yaml
autoscaling.knative.dev/maxScale: "200"  # Up from 100
```

**Capacity**: 200 instances × 100 = **20,000 concurrent requests**

**Note**: Requires Team tier (400 connections) or Enterprise tier for this scale.

### Option 3: Optimize for Cost (Lower Concurrency)

**For**: Cost optimization with acceptable latency

```yaml
containerConcurrency: 80   # Lower concurrency
autoscaling.knative.dev/minScale: "1"  # Fewer warm instances
```

**Trade-off**: More instances needed, but lower cost per request during low traffic.

## Database Connection Limits by Supabase Tier

| Tier | Max Connections | Recommended Max Instances | Max Concurrent Users |
|------|----------------|---------------------------|---------------------|
| Free | 60 | 10-20 | 1,000-2,000 |
| Pro | 200 | 50-100 | 5,000-10,000 |
| Team | 400 | 100-200 | 10,000-20,000 |
| Enterprise | Custom | 200+ | 20,000+ |

**Current Configuration**: Optimized for Pro tier (200 connections)

## Monitoring & Optimization

### Key Metrics to Monitor

1. **Cloud Run Metrics**:
   - Request count per instance
   - Instance count (autoscaling)
   - Request latency (p50, p95, p99)
   - Error rate

2. **Database Metrics**:
   - Active connections
   - Connection pool utilization
   - Query latency
   - Connection wait time

3. **Application Metrics**:
   - Connection pool exhaustion errors
   - Request timeouts
   - External API rate limits (OpenAI, Anthropic, etc.)

### When to Scale Up

- **Increase Concurrency**: When instances are underutilized (< 50% CPU)
- **Increase Max Instances**: When hitting max instances frequently
- **Increase DB Pool**: When seeing connection timeout errors

### When to Scale Down

- **Decrease Concurrency**: When seeing high latency or connection errors
- **Decrease Min Instances**: During low-traffic periods to save costs
- **Decrease DB Pool**: If hitting Supabase connection limits

## External API Rate Limits

Your application depends on external APIs that may have rate limits:

### OpenAI
- **Rate Limits**: Varies by tier (Free: 3 RPM, Pay-as-you-go: 500 RPM per model)
- **Recommendation**: Monitor usage and upgrade tier if needed

### Anthropic
- **Rate Limits**: Varies by tier
- **Recommendation**: Implement request queuing if hitting limits

### Pinecone
- **Rate Limits**: Based on plan
- **Recommendation**: Monitor query volume and upgrade if needed

### Supabase (Database)
- **Connection Limits**: See table above
- **Recommendation**: Monitor active connections and upgrade tier if needed

## Best Practices

1. **Connection Pooling**: Always use PgBouncer (transaction pooling mode)
2. **Health Checks**: Ensure `/` endpoint responds quickly (< 100ms)
3. **Graceful Degradation**: Handle rate limits and connection errors gracefully
4. **Monitoring**: Set up alerts for:
   - High error rates
   - Connection pool exhaustion
   - High latency (p95 > 2s)
   - Max instances reached

5. **Cost Optimization**:
   - Use min instances = 1-2 during low traffic
   - Monitor and optimize resource requests
   - Consider reserved capacity for predictable workloads

## Troubleshooting

### "QueuePool limit reached" Error

**Cause**: Too many concurrent requests trying to use database connections

**Solutions**:
1. Increase `DB_POOL_SIZE` and `DB_MAX_OVERFLOW`
2. Increase `containerConcurrency` (fewer instances needed)
3. Optimize queries to be faster (reduce connection hold time)
4. Check for connection leaks (sessions not being closed)

### High Latency

**Causes**:
- Too high concurrency per instance
- Database connection wait time
- External API rate limiting

**Solutions**:
1. Reduce `containerConcurrency`
2. Increase database connection pool
3. Implement caching for frequently accessed data
4. Optimize slow queries

### Cold Starts

**Cause**: No warm instances available

**Solutions**:
1. Increase `minScale` (more warm instances)
2. Optimize container startup time
3. Use Cloud Run min instances feature

## Next Steps

1. **Monitor** your current usage patterns
2. **Test** load with expected traffic levels
3. **Adjust** configuration based on metrics
4. **Upgrade** Supabase tier if hitting connection limits
5. **Implement** caching for frequently accessed data (Redis/Memorystore)

## References

- [Cloud Run Autoscaling](https://cloud.google.com/run/docs/configuring/services/autoscaling)
- [Cloud Run Concurrency](https://cloud.google.com/run/docs/configuring/concurrency)
- [Supabase Connection Pooling](https://supabase.com/docs/guides/database/connecting-to-postgres#connection-pooler)
- [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)
