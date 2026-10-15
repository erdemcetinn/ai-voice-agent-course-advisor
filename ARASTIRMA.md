# Araştırma Notları

Projede kullanılan, AWS dokümanlarından doğrulanmış bilgiler. Son kontrol: 14 Ekim 2026.
"Doğrulanacak" yazan maddeler henüz test edilmedi.

---

## 1. Bu tür sistemin adı ne?

**Voice AI agent** (sesli yapay zeka ajanı). Kullanılan terimler:

| Terim | Anlamı |
|---|---|
| **Cascaded pipeline** | Ses metne çevrilir, LLM metni işler, cevap tekrar sese çevrilir. Üç ayrı adım. **Connect'in agentic voice'u böyle çalışıyor** |
| **Speech-to-speech** | Tek model, ses girer ses çıkar, arada metin yok (ör. Amazon Nova Sonic, OpenAI Realtime) |
| **Endpointing (turn detection)** | Arayanın sözünü bitirip bitirmediğine karar vermek |
| **Barge-in** | Bot konuşurken arayanın sözü kesebilmesi |
| **Latency masking** | Tool beklenirken "bir saniye bakıyorum" gibi ara cümle söylemek |
| **RAG** | Retrieval-Augmented Generation. LLM'e cevap vermeden önce ilgili bilgiyi bulup vermek |

---

## 2. Amazon Connect agentic self-service nasıl çalışıyor?

Kaynak: [agentic-self-service](https://docs.aws.amazon.com/connect/latest/adminguide/agentic-self-service.html)

- **Orkestratör AI agent** birden fazla adımda düşünebiliyor, tool çağırabiliyor ve konuşmayı sorun çözülene kadar sürdürüyor. Eski "legacy self-service"de ise her tool çağrısında kontrol akışa geri dönüyordu.
- Ajan, listeden seçilen bir LLM kullanıyor. AWS'in örnekleri Amazon Nova Pro ve Anthropic Claude Sonnet ([kaynak](https://aws.amazon.com/about-aws/whats-new/2025/09/amazon-q-connect-selecting-llms-connect-web-ui)).
- Contact flow'daki `Get customer input` bloğu hala bir **Lex botu** üzerinden çalışıyor. Lex ortadan kalkmadı, taşıyıcı katman olarak kalıyor.
- Ajanın cevapları `<message>` etiketleri içinde olmalı, yoksa arayan mesajı duymuyor.
- **Bölge:** `us-east-1` ve `us-west-2`.

### Üç tool tipi

| Tip | Ne yapar |
|---|---|
| **MCP tool** | Backend'e bağlanır. Ajan çağırırken konuşma devam eder |
| **Return to Control** | Konuşmayı bitirir ve kontrolü akışa verir. Varsayılanlar: `Complete`, `Escalate` |
| **Constant** | Sabit bir metin döndürür. Backend hazır değilken test etmek için |

### Tool ayarları
Kaynak: [ai-agent-mcp-tools](https://docs.aws.amazon.com/connect/latest/adminguide/ai-agent-mcp-tools.html)

- Her tool'a ek talimat yazılabiliyor, **girdi değerleri sabitlenebiliyor (override input values)**, çıktı filtrelenebiliyor.
- **Bir tool çağrısı en fazla 30 saniye sürebilir.**
- Hangi tool'lara erişilebileceğini **security profile** belirliyor. Bu, insan çalışanlar için kullanılan sistemle aynı.
- **Doğrulanacak:** Override'ın bir contact attribute'tan (ör. doğrulanmış `studentId`) değer okuyup okuyamadığı.

---

## 3. Kendi tool'larımızı Connect'e bağlamak

Kaynak: [3p-apps-mcp-server](https://docs.aws.amazon.com/connect/latest/adminguide/3p-apps-mcp-server.html)

İki yol var: **flow module tool'ları** ya da **Bedrock AgentCore Gateway**. Biz Gateway'i kullanıyoruz, çünkü dokümanı ve örneği daha net.

- Gateway "API'leri, Lambda fonksiyonlarını ve servisleri MCP uyumlu tool'lara dönüştürüyor". Yani **kendi MCP server'ımızı yazmamıza gerek yok.**
- **Inbound auth:** JWT. Discovery URL formatı: `https://<instance>.my.connect.aws/.well-known/openid-configuration`
- **Allowed audiences:** gateway'in kendi ID'si olmalı. Connect'in gönderdiği token'da bu ID var, eksikse gateway isteği reddediyor. Doldurulması zorunlu olan tek alan bu.
- **Supported versions:** `2025-03-26` (Connect'in desteklediği MCP sürümü) listede olmalı.
- Bir gateway sadece bir Connect instance'ına bağlanabiliyor.
- **Doğrulanacak:** Lambda hedefinde Gateway'in çağrılan tool'un adını Lambda'ya nasıl ilettiği.

### Başkasının deneyiminden uyarılar
Kaynak: [Classmethod blog yazısı](https://dev.classmethod.jp/articles/amazon-connect-ai-agent-mcp-bedrock-agentcore-gateway/) (API Gateway hedefi ile denenmiş, Lambda ile değil)

- Gateway ID değişince hedef ayarları sıfırlanmış, tekrar girmek gerekmiş.
- Şema değişikliklerinin tool listesinde görünmesi birkaç dakika sürmüş.
- Claude Sonnet ile bir tool'lu cevap 7 ile 10 saniye sürmüş. Bizde de gecikmeyi ölçmek gerekecek.

---

## 4. Ses ayarları (agentic voice)

Kaynak: [agentic-voice-best-practices](https://docs.aws.amazon.com/connect/latest/adminguide/agentic-voice-best-practices.html)

Connect agentic voice iki parçadan oluşuyor: **Advanced ASR** (sesi metne çeviriyor ve cümle sonunu tahmin ediyor) ve **ses motoru** (metni sese çeviriyor).

### Cümle sonu (endpointing)
Sistem iki koşuldan biri önce gerçekleşince sırayı bitiriyor:

| Ayar | Session attribute | Varsayılan | Aralık |
|---|---|---|---|
| Güven eşiği (asıl sinyal) | `x-amz-lex:audio:end-confidence-threshold` | 0.7 | 0.5 ile 0.9 |
| Sessizlik süresi (yedek) | `x-amz-lex:audio:end-timeout-ms` | 640 ms | 500 ile 10.000 ms |

- Hesap numarası gibi tuşlanan ya da dikte edilen bilgiler için AWS'in önerisi: eşik 0.9, süre 6000 ile 8000 ms. Bilgi alındıktan sonra varsayılana geri dön.
- Ayarlar `x-amz-lex:audio:<ayar>:<intent>:<slot>` biçiminde, belirli bir adıma özel verilebiliyor.

### Söz kesme (barge-in)
- `x-amz-lex:allow-interrupt`, varsayılan `true`. Sadece yasal uyarılar gibi sonuna kadar dinlenmesi gereken yerlerde kapat.
- Arayan sustuğunda botun kendiliğinden konuşması söz kesme değil, cümle sonu ayarının tetiklenmesi. Çözümü cümle sonu ayarlarında.

### Sesli çıktı kuralları
- Markdown, liste, emoji, parantez kullanma. Ses motoru bunları sesli okuyor.
- BÜYÜK HARF harf harf okunuyor (`ACME` "A-C-M-E" olur). Kodları harf harf okutmak için `<spell>` etiketi kullanılıyor.
- Uzun tool çağrılarında arayanı sessizlikte bırakma. "Bir saniye, bakıyorum" gibi bir dolgu cümlesi ya da bekleme sesi kullan.

---

## 5. Diğer seçenekler (bilgi için)

| Platform | Özellik |
|---|---|
| **Vapi, Retell, Bland, ElevenLabs Agents** | Hazır sesli ajan platformları, dakika başı ücretli |
| **LiveKit Agents, Pipecat** | Açık kaynak, kendin barındırıyorsun, kodla yazılıyor |
| **AWS AgentCore + Strands + Nova Sonic** | AWS'in tarayıcı tabanlı speech-to-speech referans mimarisi. Telefon yok |

Yüksek öğrenimde mevcut ürünlerin neredeyse hepsi (Mainstay, Ivy.ai, Ocelot, Element451) **yazılı chatbot.** Sesli ders danışmanlığı az bulunan bir alan.

---

## 6. Düzeltilen eski bilgiler

Eski araştırmada (8 Ekim) yanlış olan ve düzeltilen bilgiler:

| Eski iddia | Doğrusu |
|---|---|
| Connect yolu Nova Sonic ile speech-to-speech çalışıyor | Connect agentic voice cascaded çalışıyor: Advanced ASR, seçilen LLM, ses motoru |
| Lex artık eski bir yol | Lex taşıyıcı katman olarak hala kullanılıyor |
| Kendi MCP server'ımızı yazmamız gerekiyor | AgentCore Gateway Lambda'yı MCP tool'una çeviriyor |
| Arama için FAISS | Birkaç yüz parça için numpy yeterli |
| Dersler INFO kodlu, 32 kredi, ön koşulda B- | CPS Informatics dersleri ITC kodlu, 34 kredi, ön koşulda C- (bölüm 7) |

---

## 7. Katalog: CPS MPS in Informatics (doğrulandı, 14 Ekim 2026)

Kaynak: [program sayfası, 2026-2027 kataloğu](https://catalog.northeastern.edu/graduate/professional-studies/masters-degree-programs/informatics-mps/) ve [ITC ders açıklamaları](https://catalog.northeastern.edu/course-descriptions/itc/). Faz 1'deki betik bunları sayfanın kendisinden tekrar kontrol edecek.

- Ders kodu **ITC.** INFO kodlu dersler (INFO 5100 gibi) mühendislik fakültesinin başka bir programına ait.
- Program 2026 güzünden itibaren çeyrek (quarter) sisteminden **dönem (semester)** sistemine geçti. Katalogdaki "semester hours" = **kredi.**
- **Toplam 34 kredi, minimum GPA 3.000.**
- **Zorunlu (18 kredi):** ITC 6105 (3), ITC 6150 (3), ITC 6205 (3), ITC 6250 (3), PJM 6440 (2), ITC 6980 Capstone (4).
- **Kalan 16 kredi:** bir konsantrasyon (zorunlu değil) ya da seçmeli seçeneği.
  - Konsantrasyonlar: AI Systems and Data Management, Analytics, Cloud Computing Application and Management, Human-Centered Informatics, Information Security Management, Project Management.
  - Seçmeli seçeneği: herhangi bir CPS lisansüstü dersinden 12 kredi + kısıtlı seçmelilerden 4 kredi.
  - Kısıtlı seçmeliler: INT 6940, ITC 6405, ITC 6415, ITC 6435, ITC 6480, ITC 6680, ITC 6983.
- **Ön koşullu lisansüstü ITC dersleri** (minimum not hep C-):

  | Ders | Ön koşul |
  |---|---|
  | ITC 6640 | ITC 6300 veya ITC 6610 |
  | ITC 6680 | ITC 6610 ve ITC 6620 |
  | ITC 6721 | AAI 6600 veya ALY 6420 veya ITC 6150 |
  | ITC 6730 | AAI 6600 veya ALY 6420 veya ITC 6711 |
  | ITC 6980 | (ITC 6105, 6150, 6205, 6250, PJM 6440 hepsi) veya (INT 6940, ITC 6000, 6010, 6020, 6035, 6400 hepsi; eski çeyrek sistemi) |

- **Katalogda olmayan bilgiler:** bir dersin iki konsantrasyona sayılıp sayılmadığı (ITC 6630 Cloud ve Security'de var), transfer kredisi, ders tekrarı, dersin hangi dönem açıldığı.
