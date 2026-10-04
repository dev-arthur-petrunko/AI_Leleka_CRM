import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AlertTriangle, Banknote, Crown, Repeat, ShoppingCart, TrendingUp, Users } from 'lucide-react';
import { api } from '../api';
import { useCountUp } from '../hooks/useCountUp';
import { Card, Badge, EmptyState, ErrorState, Skeleton, Tabs } from '../components/ui';
import { t } from '../i18n';

const PERIODS = ['7', '30', '90'];

type RevDay = { day: string; total: number; count: number };

function sumTotal(byDay: RevDay[]): number {
  return byDay.reduce((a, d) => a + (Number(d.total) || 0), 0);
}
function sumCount(byDay: RevDay[]): number {
  return byDay.reduce((a, d) => a + (Number(d.count) || 0), 0);
}

export default function Analytics() {
  const [days, setDays] = useState('30');
  const rev = useQuery({
    queryKey: ['rev', days], queryFn: () => api<{ by_day: RevDay[]; aov: number }>(`/analytics/shop/revenue?days=${days}`),
  });
  const dash = useQuery({
    queryKey: ['dash'], queryFn: () => api<any>('/analytics/dashboard'), retry: false,
  });
  const ltv = useQuery({
    queryKey: ['ltv'], queryFn: () => api<{ top: { name: string; ltv: number; orders: number }[]; repeat_rate: number }>('/analytics/shop/ltv?limit=7'), retry: false,
  });
  const returns = useQuery({
    queryKey: ['returns'], queryFn: () => api<{ rate: number; count: number; by_reason: Record<string, number>; lost_revenue: number }>('/analytics/shop/returns'), retry: false,
  });
  const loss = useQuery({
    queryKey: ['loss'], queryFn: () => api<Record<string, number>>('/analytics/loss-reasons'), retry: false,
  });
  const rfm = useQuery({
    queryKey: ['rfm'], queryFn: () => api<{ client_id: string; r: number; f: number; m: number }[]>('/analytics/shop/rfm'), retry: false,
  });
  const frange = useQuery({
    queryKey: ['frange'],
    queryFn: () => api<{ weighted_pipeline: number; moving_avg: number; range: [number, number] }>('/analytics/shop/forecast-range'),
    retry: false,
  });

  const loading = rev.isLoading || dash.isLoading;
  if (loading) return <Card><Skeleton rows={6} /></Card>;
  if (rev.error || !rev.data) {
    return <Card><ErrorState onRetry={() => rev.refetch()} /></Card>;
  }

  const byDay = rev.data.by_day || [];
  const revenueSum = sumTotal(byDay);
  const ordersSum = sumCount(byDay);
  const kpi = dash.data?.kpi;
  const funnel = dash.data?.funnel || [];
  const forecast = dash.data?.forecast;
  const lossEntries = Object.entries(loss.data || {}).sort((a, b) => b[1] - a[1]).slice(0, 6);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0, fontSize: 20 }}>Аналітика</h2>
        <span style={{ flex: 1 }} />
        <Tabs tabs={PERIODS.map((p) => `${p} днів`)} value={`${days} днів`}
          onChange={(v) => setDays(v.split(' ')[0])} />
      </div>

      {dash.error && (
        <Card style={{ borderLeft: '4px solid var(--warning)', padding: '12px 16px' }}>
          <b>Розширена аналітика недоступна на вашому тарифі.</b>{' '}
          <span style={{ color: 'var(--text-muted)' }}>Виручка магазину нижче — з ваших даних. Воронка і прогноз зʼявляться після апгрейду.</span>{' '}
          <Link to="/settings" style={{ color: 'var(--link)' }}>До тарифу</Link>
        </Card>
      )}

      <KpiRow
        revenue={revenueSum} orders={ordersSum} aov={rev.data.aov}
        leads={kpi?.new_leads_30d} conversion={kpi?.conversion} avgCheck={kpi?.avg_check}
        repeatRate={ltv.data?.repeat_rate} returnRate={returns.data?.rate}
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(330px,1fr))', gap: 14 }}>
        <Card>
          <h3 style={{ marginTop: 0 }}>Виручка по днях</h3>
          {byDay.length === 0 ? (
            <EmptyState title="Поки порожньо" hint="Дані зʼявляться після перших оплачених замовлень." />
          ) : (
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={byDay} margin={{ top: 16 }}>
                <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} domain={[0, 'auto']} allowDecimals={false} width={48} />
                <Tooltip />
                <Bar dataKey="total" name="Виручка, ₴" fill="var(--info)" radius={[6, 6, 0, 0]}
                  label={{ position: 'top', fontSize: 10, fill: 'var(--text-muted)' }} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card>
          <h3 style={{ marginTop: 0 }}>Замовлення по днях</h3>
          {byDay.length === 0 ? (
            <EmptyState title="Поки порожньо" hint="Дані зʼявляться після перших замовлень." />
          ) : (
            <ResponsiveContainer width="100%" height={230}>
              <LineChart data={byDay}>
                <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} domain={[0, 'auto']} allowDecimals={false} width={40} />
                <Tooltip />
                <Line type="monotone" dataKey="count" name="Замовлень" stroke="var(--success)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(330px,1fr))', gap: 14 }}>
        <Card>
          <h3 style={{ marginTop: 0 }}>Воронка угод</h3>
          {funnel.length === 0 ? (
            <EmptyState title={dash.error ? 'Потрібен апгрейд тарифу' : 'Немає угод'}
              hint={dash.error ? 'Воронка доступна на платному тарифі.' : 'Створіть першу угоду — тут буде воронка з % переходу.'}
              action={!dash.error ? <Link to="/deals" style={{ color: 'var(--link)' }}>До угод</Link> : undefined} />
          ) : (
            <FunnelChart data={funnel} />
          )}
        </Card>
        <Card>
          <h3 style={{ marginTop: 0 }}>Прогноз виручки</h3>
          {!forecast || !forecast.history?.length ? (
            <EmptyState title="Прогнозу поки немає" hint="Потрібні виграні угоди за кілька місяців." />
          ) : (
            <ForecastChart history={forecast.history.map((h: any) => ({ m: h.month, v: h.total }))}
              next={forecast.forecast_next_month} />
          )}
          {typeof forecast?.forecast_next_month === 'number' && (
            <div className="num" style={{ marginTop: 8, fontWeight: 800, fontSize: 16 }}>
              Наступний місяць: {Math.round(forecast.forecast_next_month).toLocaleString('uk-UA')} ₴
            </div>
          )}
        </Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(330px,1fr))', gap: 14 }}>
        <Card>
          <h3 style={{ marginTop: 0 }}>Наступні дії (AI)</h3>
          <NextActions data={dash.data?.next_actions} insight={dash.data?.ai_insight}
            blocked={!!dash.error} />
        </Card>
        <Card>
          <h3 style={{ marginTop: 0 }}>Ризик відтоку</h3>
          <ChurnCard data={dash.data?.churn} blocked={!!dash.error} />
        </Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(330px,1fr))', gap: 14 }}>
        <Card>
          <h3 style={{ marginTop: 0, display: 'flex', gap: 8, alignItems: 'center' }}>
            <Crown size={17} aria-hidden /> Топ клієнтів за LTV
          </h3>
          {!ltv.data || ltv.data.top.length === 0 ? (
            <EmptyState title="Поки порожньо" hint="LTV рахується з оплачених замовлень." />
          ) : (
            <div>
              {ltv.data.top.map((row, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'baseline', padding: '7px 0',
                  borderTop: i ? '1px solid var(--border)' : 'none' }}>
                  <b style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {row.name || 'Без імені'}
                  </b>
                  <span className="num" style={{ color: 'var(--text-muted)', fontSize: 12 }}>{row.orders} зам.</span>
                  <b className="num">{Math.round(row.ltv).toLocaleString('uk-UA')} ₴</b>
                </div>
              ))}
              <div style={{ marginTop: 8, fontSize: 13, color: 'var(--text-muted)' }}>
                Повторні покупки: <b className="num" style={{ color: 'var(--text)' }}>{Math.round((ltv.data.repeat_rate || 0) * 100)}%</b>
              </div>
            </div>
          )}
        </Card>
        <Card>
          <h3 style={{ marginTop: 0, display: 'flex', gap: 8, alignItems: 'center' }}>
            <AlertTriangle size={17} aria-hidden /> Втрати: причини і повернення
          </h3>
          {lossEntries.length === 0 && !returns.data?.count ? (
            <EmptyState title="Втрат не зафіксовано" hint="Програшні угоди і повернення зʼявляться тут." />
          ) : (
            <div>
              {lossEntries.map(([reason, n]) => (
                <LossRow key={reason} reason={reason} count={n}
                  total={lossEntries.reduce((a, [, x]) => a + x, 0)} />
              ))}
              {!!returns.data && (
                <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)', fontSize: 13 }}>
                  <div>Повернень: <b className="num">{returns.data.count}</b>
                    {' '}({Math.round((returns.data.rate || 0) * 100)}% замовлень)</div>
                  <div>Втрачено на поверненнях: <b className="num">
                    {Math.round(returns.data.lost_revenue || 0).toLocaleString('uk-UA')} ₴</b></div>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(330px,1fr))', gap: 14 }}>
        <Card>
          <h3 style={{ marginTop: 0 }}>RFM-сегменти</h3>
          <RfmCard data={rfm.data} loading={rfm.isLoading} error={!!rfm.error} retry={() => rfm.refetch()} />
        </Card>
        <Card>
          <h3 style={{ marginTop: 0 }}>Прогноз діапазоном</h3>
          <RangeCard data={frange.data} loading={frange.isLoading} error={!!frange.error} retry={() => frange.refetch()} />
        </Card>
      </div>
    </div>
  );
}

function KpiRow(props: { revenue: number; orders: number; aov: number; leads?: number;
  conversion?: number; avgCheck?: number; repeatRate?: number; returnRate?: number }) {
  const tiles: { icon: typeof Banknote; label: string; value: number; fmt: (v: number) => string }[] = [
    { icon: Banknote, label: 'Виручка', value: props.revenue, fmt: (v) => `${Math.round(v).toLocaleString('uk-UA')} ₴` },
    { icon: ShoppingCart, label: 'Замовлень', value: props.orders, fmt: (v) => String(Math.round(v)) },
    { icon: TrendingUp, label: 'Середній чек (AOV)', value: props.aov || 0, fmt: (v) => `${Math.round(v).toLocaleString('uk-UA')} ₴` },
    ...(props.leads !== undefined ? [{ icon: Users, label: 'Нові ліди 30д', value: props.leads, fmt: (v: number) => String(Math.round(v)) }] : []),
    ...(props.conversion !== undefined ? [{ icon: TrendingUp, label: 'Конверсія в угодах', value: props.conversion * 100, fmt: (v: number) => `${Math.round(v)}%` }] : []),
    ...(props.avgCheck !== undefined ? [{ icon: Banknote, label: 'Середній чек угод', value: props.avgCheck, fmt: (v: number) => `${Math.round(v).toLocaleString('uk-UA')} ₴` }] : []),
    ...(props.repeatRate !== undefined ? [{ icon: Repeat, label: 'Повторні покупки', value: props.repeatRate * 100, fmt: (v: number) => `${Math.round(v)}%` }] : []),
    ...(props.returnRate !== undefined ? [{ icon: AlertTriangle, label: 'Повернення', value: props.returnRate * 100, fmt: (v: number) => `${Math.round(v)}%` }] : []),
  ];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 10 }}>
      {tiles.map((tl) => <KpiTile key={tl.label} {...tl} />)}
    </div>
  );
}

function KpiTile({ icon: Icon, label, value, fmt }: {
  icon: typeof Banknote; label: string; value: number; fmt: (v: number) => string;
}) {
  const v = useCountUp(value);
  return (
    <Card style={{ padding: 14 }}>
      <Icon size={17} aria-hidden style={{ color: 'var(--text-muted)' }} />
      <div className="num" style={{ fontSize: 21, fontWeight: 800, marginTop: 6 }}>{fmt(v)}</div>
      <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 2 }}>{label}</div>
    </Card>
  );
}

function FunnelChart({ data }: { data: { stage: string; count: number; sum?: number }[] }) {
  const total = data[0]?.count || 1;
  const max = Math.max(...data.map((d) => d.count), 1);
  return (
    <div>
      {data.map((f, i) => {
        const prev = i === 0 ? null : Math.round((f.count / (data[i - 1].count || 1)) * 100);
        return (
          <div key={f.stage} style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 13 }}>
              <span>{t('stage.' + f.stage)}</span>
              <span className="num"><b>{f.count}</b>
                {f.sum !== undefined && (
                  <span style={{ color: 'var(--text-muted)' }}> · {Math.round(f.sum).toLocaleString('uk-UA')} ₴</span>
                )}
              </span>
            </div>
            <div style={{ height: 14, borderRadius: 7, background: 'var(--bg-hover)', marginTop: 4 }}>
              <div style={{ width: `${Math.round((f.count / max) * 100)}%`, maxWidth: '100%', height: '100%',
                borderRadius: 7, background: 'linear-gradient(90deg,var(--info),var(--primary))' }} />
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              {i === 0 ? `${Math.round((f.count / total) * 100)}% від входу` : `→ ${prev}% з попередньої`}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function NextActions({ data, insight, blocked }: { data?: any[]; insight?: string; blocked: boolean }) {
  if (blocked) {
    return <EmptyState title="Потрібен апгрейд тарифу" hint="AI-підказки доступні на платному тарифі." />;
  }
  return (
    <div>
      {insight && (
        <p style={{ fontSize: 13, background: 'var(--bg-hover)', borderRadius: 10, padding: '8px 12px' }}>
          {insight}
        </p>
      )}
      {(!data || data.length === 0) && !insight && (
        <EmptyState title="Порад поки немає" hint="Зʼявляться, коли буде більше угод." />
      )}
      {(data || []).slice(0, 6).map((a: any, i: number) => (
        <div key={i} style={{ fontSize: 13, padding: '6px 0',
          borderTop: i ? '1px solid var(--border)' : 'none' }}>
          <Badge tone="info">Пріоритет {a.priority || ''}</Badge>{' '}
          {typeof a === 'string' ? a : `${a.action || 'дія'}: ${a.reason || ''}`}
          {a.deal_id && (
            <span className="num" style={{ color: 'var(--text-muted)' }}>
              {' '}· угода {String(a.deal_id).slice(0, 8)}
            </span>
          )}
        </div>
      ))}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
        Це пріоритет, а не точний прогноз.
      </div>
    </div>
  );
}

function ChurnCard({ data, blocked }: { data?: any[]; blocked: boolean }) {
  if (blocked) {
    return <EmptyState title="Потрібен апгрейд тарифу" hint="Ризик відтоку — на платному тарифі." />;
  }
  if (!data || data.length === 0) {
    return <EmptyState title="Ризику немає" hint="Клієнти без активності 30+ днів зʼявляться тут." />;
  }
  return (
    <div>
      {data.slice(0, 7).map((c: any, i: number) => (
        <div key={c.client_id || i} style={{ display: 'flex', gap: 8, fontSize: 13, padding: '6px 0',
          borderTop: i ? '1px solid var(--border)' : 'none' }}>
          <span style={{ flex: 1 }}>{c.name || 'Клієнт'}</span>
          <span className="num" style={{ color: 'var(--warning)' }}>
            {c.days_idle != null ? `${c.days_idle} дн без руху` : ''}
          </span>
        </div>
      ))}
    </div>
  );
}

function RfmCard({ data, loading, error, retry }: {  data?: { client_id: string; r: number; f: number; m: number }[] | null;
  loading: boolean; error: boolean; retry: () => void;
}) {
  if (loading) return <Skeleton rows={3} />;
  if (error) return <ErrorState onRetry={retry} />;
  if (!data || data.length === 0) return <EmptyState title="Поки немає даних" hint="RFM рахується з доставлених замовлень." />;
  const active = data.filter((x) => x.r >= 4).length;
  const risk = data.filter((x) => x.r <= 2).length;
  const vip = data.filter((x) => x.f + x.m >= 8).length;
  const row = (label: string, v: number, total: number) => (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
        <span>{label}</span><b className="num">{v}</b>
      </div>
      <div style={{ height: 10, borderRadius: 5, background: 'var(--bg-hover)', marginTop: 4 }}>
        <div style={{ width: `${total ? Math.round((v / total) * 100) : 0}%`, height: '100%',
          borderRadius: 5, background: 'var(--info)' }} />
      </div>
    </div>
  );
  return (
    <div>
      {row('Активні (купували нещодавно)', active, data.length)}
      {row('Ризик втрати (давно не купували)', risk, data.length)}
      {row('VIP (часто і багато)', vip, data.length)}
      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
        R/F/M — квінтилі 1–5: давність, частота, сума. Розсилку «не купували 60 днів» робіть по R ≤ 2.
      </div>
    </div>
  );
}

function RangeCard({ data, loading, error, retry }: {
  data?: { weighted_pipeline: number; moving_avg: number; range: [number, number] } | null;
  loading: boolean; error: boolean; retry: () => void;
}) {
  if (loading) return <Skeleton rows={3} />;
  if (error) return <ErrorState onRetry={retry} />;
  if (!data) return <EmptyState title="Прогнозу немає" hint="Потрібні відкриті або виграні угоди." />;
  const [lo, hi] = data.range || [0, 0];
  return (
    <div style={{ fontSize: 13 }}>
      <div>Зважена воронка: <b className="num">{Math.round(data.weighted_pipeline || 0).toLocaleString('uk-UA')} ₴</b></div>
      <div>Ковзне середнє: <b className="num">{Math.round(data.moving_avg || 0).toLocaleString('uk-UA')} ₴</b></div>
      <div style={{ marginTop: 6 }}>Діапазон наступного місяця:{' '}
        <b className="num">{Math.round(lo).toLocaleString('uk-UA')} – {Math.round(hi).toLocaleString('uk-UA')} ₴</b>
      </div>
    </div>
  );
}

function LossRow({ reason, count, total }: { reason: string; count: number; total: number }) {  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
        <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{reason}</span>
        <b className="num">{count}</b>
      </div>
      <div style={{ height: 10, borderRadius: 5, background: 'var(--bg-hover)', marginTop: 4 }}>
        <div style={{ width: `${total ? Math.round((count / total) * 100) : 0}%`, height: '100%',
          borderRadius: 5, background: 'var(--warning)' }} />
      </div>
    </div>
  );
}

function ForecastChart({ history, next }: { history: { m: string; v: number }[]; next?: number }) {
  const data = useMemo(() => {
    const base = history.map((h) => ({ m: h.m, v: h.v, f: null as number | null }));
    if (typeof next === 'number' && base.length) {
      base.push({ m: 'прогноз', v: base[base.length - 1].v, f: next });
      if (base.length > 1) base[base.length - 2].f = base[base.length - 2].v;
    }
    return base;
  }, [history, next]);
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data}>
        <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
        <XAxis dataKey="m" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
        <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} domain={[0, 'auto']} width={52} />
        <Tooltip />
        <Line type="monotone" dataKey="v" name="Факт" stroke="var(--success)" strokeWidth={2} dot={false} />
        {typeof next === 'number' && (
          <Line type="monotone" dataKey="f" name="Прогноз" stroke="var(--warning)"
            strokeWidth={2} strokeDasharray="6 4" dot={{ r: 3 }} connectNulls />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
