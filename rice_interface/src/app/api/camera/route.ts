import { readFile, writeFile } from "fs/promises";
import path from "path";

type CameraControlBody = {
  cameraRun?: boolean;
};

const configPath = path.resolve(process.cwd(), "..", "cam.json");

export const runtime = "nodejs";

async function readCameraConfig() {
  const rawConfig = await readFile(configPath, "utf-8");
  return JSON.parse(rawConfig) as Record<string, unknown>;
}

export async function GET() {
  try {
    const config = await readCameraConfig();
    return Response.json(
      { cameraRun: Boolean(config.CAMERA_RUN) },
      { status: 200 }
    );
  } catch {
    return Response.json(
      { error: "Failed to read camera state" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as CameraControlBody;

    if (typeof body.cameraRun !== "boolean") {
      return Response.json(
        { error: "cameraRun must be a boolean" },
        { status: 400 }
      );
    }

    const config = await readCameraConfig();

    config.CAMERA_RUN = body.cameraRun;

    await writeFile(configPath, `${JSON.stringify(config, null, 4)}\n`, "utf-8");

    return Response.json({ ok: true, cameraRun: body.cameraRun }, { status: 200 });
  } catch {
    return Response.json(
      { error: "Failed to update camera state" },
      { status: 500 }
    );
  }
}