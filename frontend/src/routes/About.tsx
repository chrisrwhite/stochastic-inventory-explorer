import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";

export function About(): JSX.Element {
  return (
    <div className="grid gap-4 max-w-3xl">
      <h2 className="text-2xl font-semibold tracking-tight">About</h2>
      <Card>
        <CardHeader>
          <CardTitle>What this is</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-3 leading-relaxed">
          <p>
            This demo models demand and lead-time uncertainty to compare reorder policies under
            service-level and inventory-cost tradeoffs. It is an educational stochastic-optimization
            app, not an inventory-management system or purchasing recommendation engine.
          </p>
          <p>
            All computation runs on the server against your selected scenario and parameters;
            nothing about your session is persisted between requests.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Boundaries</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-2 leading-relaxed">
          <p>This app is not:</p>
          <ul className="list-disc list-inside space-y-1 text-muted-foreground">
            <li>an ERP or inventory management system,</li>
            <li>a pantry or barcode tracker,</li>
            <li>a procurement or purchase-order execution tool,</li>
            <li>a multi-echelon supply-chain network planner.</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
