# Metin2 Fishing Bot

Bot per il gioco Metin2 che automatizza la pesca nel minigioco di pesca.

## Linguaggio consigliato
Python è la scelta migliore per questo progetto su Windows perché consente:
- catturare lo schermo con `pyautogui`
- analizzare l'immagine con `OpenCV`
- simulare movimenti del mouse e click con comportamento umano
- avviare rapidamente lo script senza compilazione

## Cosa fa il bot
- trova l'esca nell'inventario usando coordinate calibrate
- effettua un click destro sull'esca
- preme `space` per aprire la finestra di pesca
- cerca l'ombra del pesce nella finestra e la clicca quando entra nel cerchio
- esegue tre clic per completare la cattura

## Installazione
1. Apri una shell in `c:\Users\pceli\git\Metin2FishingBot`
2. Installa le dipendenze:

```bash
python -m pip install -r requirements.txt
```

## Calibrazione
Esegui:

```bash
python bot.py --calibrate
```

Segui le istruzioni sullo schermo per:
1. posizionare il mouse sull'icona dell'esca
2. selezionare l'area della finestra di pesca

Questa operazione salva le coordinate in `config.json`.

## Modalità automatica
Se vuoi provare a eliminare la calibrazione manuale, usa:

```bash
python bot.py --auto
```

Questo cerca automaticamente la finestra di Metin2 aperta, calcola una posizione di esca di default e tenta di rilevare l'area della finestra di pesca.

## Uso
Dopo la calibrazione o la configurazione automatica, avvia il bot con:

```bash
python bot.py --rounds 10
```

Modifica `--rounds` per il numero di round di pesca da eseguire.

## Avvertenze
- mantieni il gioco in primo piano
- non muovere il mouse durante l'esecuzione
- se il bot non trova il pesce, regola l'area di ricerca con `--calibrate`

## File
- `bot.py`: script principale
- `config.json`: coordinate salvate dopo calibrazione
- `requirements.txt`: librerie Python richieste
- `.gitignore`: file ignoti per Git
