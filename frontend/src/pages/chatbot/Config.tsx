import { useState } from "react";
import { api } from "../../api/client";
import { ApiError, type ChatbotInput } from "../../api/types";
import { useToast } from "../../components/Toast";
import { Button, Card, Field, Input, Textarea } from "../../components/ui";
import { useBot } from "./ChatbotLayout";

export default function ConfigPage() {
  const { bot, reload } = useBot();
  const toast = useToast();
  const [form, setForm] = useState<ChatbotInput>({
    name: bot.name,
    system_prompt: bot.system_prompt,
    tone: bot.tone,
    welcome_message: bot.welcome_message,
    model: bot.model,
    lead_enabled: bot.lead_enabled,
    lead_after_messages: bot.lead_after_messages,
    sales_phone: bot.sales_phone ?? "",
  });
  const [saving, setSaving] = useState(false);

  const set = (k: keyof ChatbotInput, v: string) => setForm({ ...form, [k]: v });

  const save = async () => {
    setSaving(true);
    try {
      await api.updateChatbot(bot.id, form);
      toast.success("Configuration saved");
      reload();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card
      title="Configuration"
      actions={
        <Button onClick={save} loading={saving}>
          Save changes
        </Button>
      }
    >
      <Field label="Name">
        <Input value={form.name} onChange={(e) => set("name", e.target.value)} />
      </Field>
      <Field label="System prompt" hint="Defines the assistant's role and rules.">
        <Textarea
          rows={4}
          value={form.system_prompt}
          onChange={(e) => set("system_prompt", e.target.value)}
        />
      </Field>
      <div className="row">
        <Field label="Tone">
          <Input value={form.tone} onChange={(e) => set("tone", e.target.value)} />
        </Field>
        <Field
          label="Model"
          hint="Groq: llama-3.1-8b-instant · llama-3.3-70b-versatile · qwen/qwen3-32b. Ollama: qwen2.5:1.5b"
        >
          <Input
            value={form.model}
            onChange={(e) => set("model", e.target.value)}
            placeholder="llama-3.1-8b-instant"
          />
        </Field>
      </div>
      <Field label="Welcome message">
        <Textarea
          rows={2}
          value={form.welcome_message}
          onChange={(e) => set("welcome_message", e.target.value)}
        />
      </Field>

      <div className="lead-settings">
        <label className="lead-toggle">
          <input
            type="checkbox"
            checked={!!form.lead_enabled}
            onChange={(e) => setForm({ ...form, lead_enabled: e.target.checked })}
          />
          <span>
            <strong>Lead capture</strong> — show a name + phone form so a
            salesperson can call back.
          </span>
        </label>
        {form.lead_enabled && (
          <Field label="Show the form after this many visitor messages">
            <Input
              type="number"
              min={1}
              max={20}
              value={form.lead_after_messages ?? 3}
              onChange={(e) =>
                setForm({
                  ...form,
                  lead_after_messages: Math.max(1, Number(e.target.value) || 1),
                })
              }
              style={{ maxWidth: 120 }}
            />
          </Field>
        )}
        <Field
          label="Sales phone"
          hint="Shown when a visitor asks for a quote/contact, or when the bot has no answer. Leave blank to hide."
        >
          <Input
            value={form.sales_phone ?? ""}
            onChange={(e) => set("sales_phone", e.target.value)}
            placeholder="1300 089 547"
          />
        </Field>
      </div>
    </Card>
  );
}
