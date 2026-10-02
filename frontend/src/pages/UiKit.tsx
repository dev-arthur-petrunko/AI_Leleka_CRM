import { Badge, Button, Card, Checkbox, EmptyState, ErrorState, Input, Select, Skeleton, Tabs } from '../components/ui';

export default function UiKit() {
  return (
    <div>
      <h2>UI-kit (обидві теми)</h2>
      <Card style={{ marginBottom: 12 }}>
        <h3>Кнопки</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button>Primary</Button><Button variant="ghost">Ghost</Button><Button variant="danger">Danger</Button>
        </div>
      </Card>
      <Card style={{ marginBottom: 12 }}>
        <h3>Поля</h3>
        <Input placeholder="Текст" />
        <div style={{ height: 8 }} />
        <Select><option>A</option><option>B</option></Select>
        <div style={{ height: 8 }} />
        <Checkbox aria-label="Згода" /> згода
      </Card>
      <Card style={{ marginBottom: 12 }}>
        <h3>Бейджі</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <Badge>info</Badge><Badge tone="ok">ok</Badge><Badge tone="warn">warn</Badge><Badge tone="bad">bad</Badge>
        </div>
      </Card>
      <Card style={{ marginBottom: 12 }}>
        <h3>Стани</h3>
        <Skeleton rows={2} />
        <EmptyState title="Порожньо" hint="Кнопка дії нижче" action={<Button>Додати</Button>} />
        <ErrorState onRetry={() => undefined} />
        <Tabs tabs={['A', 'B']} value="A" onChange={() => undefined} />
      </Card>
    </div>
  );
}
